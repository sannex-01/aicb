import json
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.models.release import ReleaseNote
from app.telemetry.sync_worker import perform_sannex_sync, get_support_config

router = APIRouter(prefix="/system", tags=["System & Releases"])


class ReleaseNoteResponse(BaseModel):
    id: Optional[int] = None
    version: str
    title: str
    description: Optional[str] = None
    changelog: List[str] = []
    release_date: Optional[str] = None
    is_critical: bool = False
    download_url: Optional[str] = None


class SystemVersionResponse(BaseModel):
    name: str
    version: str
    environment: str
    sannex_host: str
    support: Optional[Dict[str, Any]] = None


@router.get("/version", response_model=SystemVersionResponse)
async def get_system_version():
    """Retrieve the current running application version, instance info, and support configuration."""
    return SystemVersionResponse(
        name=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        sannex_host=settings.SANNEX_HOST,
        support=get_support_config(),
    )


@router.get("/support")
async def get_system_support_info():
    """Retrieve the latest community support and donation settings."""
    return get_support_config()


@router.get("/releases", response_model=List[ReleaseNoteResponse])
async def list_release_notes(db: AsyncSession = Depends(get_db)):
    """Retrieve all synchronized release notes and changelogs."""
    stmt = select(ReleaseNote).order_by(desc(ReleaseNote.id))
    result = await db.scalars(stmt)
    records = result.all()

    if not records:
        # Provide current version fallback if no releases have been synced yet
        return [
            ReleaseNoteResponse(
                id=1,
                version=settings.APP_VERSION,
                title="AICB Stable Operations",
                description="Core AI Commerce and Operations Platform with Multi-Agent Studio, Access Groups, and Communication Channels.",
                changelog=[
                    "Multi-Agent Studio with custom Access Groups and LLM Provider overrides",
                    "Dynamic Communication Channels (WhatsApp, Telegram, Live Widget)",
                    "Granular payment and storage runtime configuration",
                    "AgentOS telemetry and real-time release notes synchronization",
                ],
                release_date="2026-09-05",
                is_critical=False,
            )
        ]

    response_list: List[ReleaseNoteResponse] = []
    for r in records:
        try:
            cl = json.loads(r.changelog_json) if r.changelog_json else []
            if not isinstance(cl, list):
                cl = [str(cl)]
        except Exception:
            cl = []

        response_list.append(
            ReleaseNoteResponse(
                id=r.id,
                version=r.version,
                title=r.title,
                description=r.description,
                changelog=cl,
                release_date=r.release_date,
                is_critical=r.is_critical or False,
                download_url=r.download_url,
            )
        )

    return response_list


@router.post("/releases/sync")
async def sync_system_releases(db: AsyncSession = Depends(get_db)):
    """Trigger a manual synchronization of release notes from AgentOS."""
    sync_result = await perform_sannex_sync(db)
    releases = await list_release_notes(db)
    return {
        "status": "success",
        "sync_summary": sync_result,
        "releases": releases,
    }
