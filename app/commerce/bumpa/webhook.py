import json
from fastapi import APIRouter, Request, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.logger import logger
from app.commerce.catalog_provider import CatalogManager

router = APIRouter(prefix="/webhooks/bumpa", tags=["Bumpa Webhooks"])


@router.post("")
async def handle_bumpa_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receives product/inventory/order update events from Bumpa."""
    raw_body = await request.body()
    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    event = data.get("event")
    logger.info(f"Bumpa webhook event received: {event}")

    # On product update or inventory change, sync local catalog
    if event in ["product.created", "product.updated", "inventory.updated"]:
        await CatalogManager.sync_external_catalog(db, source="bumpa")

    return {"status": "ok"}
