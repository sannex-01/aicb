import json
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.core.config import settings
from app.core.database import get_db, AsyncSessionLocal
from app.core.logger import logger
from app.models.config_override import ConfigOverride
from app.models.catalog import CatalogItem
from app.models.knowledge import KnowledgeDoc
from app.commerce.catalog_provider import CatalogManager

router = APIRouter(prefix="/sync", tags=["Telemetry & Remote Sync"])
scheduler = AsyncIOScheduler()


from sannex_agent import AsyncSannexClient

async def perform_sannex_sync(db: AsyncSession) -> Dict[str, Any]:
    """Pulls latest prompts, LLM parameters, catalogs, and knowledge docs from AgentOS/Sannex."""
    logger.info("Executing Sannex AgentOS Remote Synchronization...")
    summary: Dict[str, Any] = {
        "status": "success",
        "overrides_updated": 0,
        "knowledge_docs_synced": 0,
        "catalog_items_synced": 0,
    }

    if not settings.SANNEX_API_KEY:
        logger.info("SANNEX_API_KEY not configured. Running local catalog sync only.")
        summary["catalog_items_synced"] = await CatalogManager.sync_external_catalog(db)
        return summary

    try:
        async with AsyncSannexClient(api_key=settings.SANNEX_API_KEY, host=settings.SANNEX_HOST) as client:
            config_resp = await client.get_config()
            
            # The SDK returns a Pydantic model. We convert it to dict for easy access, or access attributes directly
            data = config_resp.model_dump()
            config = data.get("config", {})

            # 1. Update Config Overrides (Prompt, Temp, Model, etc.)
            for key in ["system_prompt", "temperature", "model_name", "llm_provider", "bot_mode", "max_tokens", "memory_window_size", "widget_profile_collection"]:
                if key in config and config[key] is not None:
                    val_str = str(config[key])
                    stmt = select(ConfigOverride).where(ConfigOverride.key == key)
                    result = await db.execute(stmt)
                    override = result.scalars().first()
                    if override:
                        override.value = val_str
                    else:
                        db.add(ConfigOverride(key=key, value=val_str))
                    summary["overrides_updated"] += 1

            # 2. Sync Knowledge Base Documents
            docs = data.get("knowledge_docs", [])
            for d in docs:
                ext_id = str(d.get("id"))
                stmt = select(KnowledgeDoc).where(KnowledgeDoc.external_id == ext_id)
                result = await db.execute(stmt)
                kdoc = result.scalars().first()
                if kdoc:
                    kdoc.title = d.get("title", kdoc.title)
                    kdoc.content = d.get("content", kdoc.content)
                    kdoc.category = d.get("category", kdoc.category)
                    kdoc.tags = d.get("tags", kdoc.tags)
                    if "embedding" in d:
                        kdoc.embedding_json = json.dumps(d["embedding"])
                else:
                    db.add(KnowledgeDoc(
                        external_id=ext_id,
                        title=d.get("title", "Untitled"),
                        content=d.get("content", ""),
                        category=d.get("category"),
                        tags=d.get("tags"),
                        embedding_json=json.dumps(d.get("embedding")) if "embedding" in d else None,
                    ))
                summary["knowledge_docs_synced"] += 1

            # 3. Sync Remote Catalog items if provided
            catalog_items = data.get("catalog_items", [])
            for p in catalog_items:
                ext_id = str(p.get("id"))
                stmt = select(CatalogItem).where(CatalogItem.external_id == ext_id, CatalogItem.source == "agentos")
                result = await db.execute(stmt)
                c_item = result.scalars().first()
                if c_item:
                    c_item.title = p.get("title", c_item.title)
                    c_item.description = p.get("description", c_item.description)
                    c_item.price = float(p.get("price", c_item.price))
                    c_item.currency = p.get("currency", c_item.currency)
                else:
                    db.add(CatalogItem(
                        source="agentos",
                        external_id=ext_id,
                        title=p.get("title", "Product"),
                        description=p.get("description"),
                        price=float(p.get("price", 0.0)),
                        currency=p.get("currency", "NGN"),
                    ))
                summary["catalog_items_synced"] += 1

            await db.commit()
            logger.info(f"AgentOS Sync completed: {summary}")

    except Exception as e:
        logger.error(f"Error during Sannex AgentOS sync: {e}")

    # Also run Paystack/Bumpa external catalog sync
    ext_synced = await CatalogManager.sync_external_catalog(db)
    summary["catalog_items_synced"] += ext_synced

    return summary


@router.post("")
async def trigger_manual_sync(db: AsyncSession = Depends(get_db)):
    """Manual sync trigger (e.g. from AgentOS dashboard or admin API)."""
    return await perform_sannex_sync(db)


async def _scheduled_sync_job():
    """Background wrapper for APScheduler."""
    async with AsyncSessionLocal() as session:
        try:
            await perform_sannex_sync(session)
        except Exception as e:
            logger.error(f"Scheduled sync failed: {e}")
        finally:
            await session.close()


def start_sync_scheduler():
    """Starts the periodic background sync job and triggers an immediate sync on startup."""
    hours = max(settings.SYNC_INTERVAL_HOURS, 1)
    scheduler.add_job(_scheduled_sync_job, "interval", hours=hours, id="sannex_sync_job", replace_existing=True)
    scheduler.start()
    logger.info(f"Sannex 12-hour periodic sync worker started (Interval: {hours}h).")

    # Trigger immediate sync in background on container startup so catalogs and prompts are never stale or empty
    asyncio.create_task(_scheduled_sync_job())


def shutdown_sync_scheduler():
    if scheduler.running:
        scheduler.shutdown()
        logger.info("Sannex sync worker shut down.")
