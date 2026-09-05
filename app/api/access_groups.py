import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user, require_admin_role
from app.models.user import AdminUser
from app.models.access_group import AccessGroup
from app.models.agent import Agent
from app.core.access import parse_tags_json

router = APIRouter(prefix="/access-groups", tags=["Access Groups & Tagging"])


class AccessGroupCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = []
    llm_provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None


class AccessGroupUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    llm_provider: Optional[str] = None
    api_key: Optional[str] = None
    model_name: Optional[str] = None


def _mask_api_key(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    val = val.strip()
    if len(val) <= 8:
        return "••••••••"
    return f"{val[:4]}••••••••{val[-4:]}"


def _serialize_group(g: AccessGroup, agent_count: int = 0) -> dict:
    return {
        "id": g.id,
        "name": g.name,
        "description": g.description,
        "tags": parse_tags_json(g.tags_json),
        "llm_provider": g.llm_provider,
        "has_api_key": bool(g.api_key),
        "api_key_masked": _mask_api_key(g.api_key),
        "model_name": g.model_name,
        "agents_count": agent_count,
        "created_at": g.created_at,
        "updated_at": g.updated_at,
    }


@router.get("")
async def list_access_groups(
    current_user: AdminUser = Depends(get_current_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Lists all Access Groups on this instance."""
    res = await db.execute(select(AccessGroup).order_by(AccessGroup.name.asc()))
    groups = res.scalars().all()

    # Get agents count per group
    agent_res = await db.execute(select(Agent))
    all_agents = agent_res.scalars().all()
    
    counts = {}
    for a in all_agents:
        from app.core.access import get_agent_group_ids
        for gid in get_agent_group_ids(a):
            counts[gid] = counts.get(gid, 0) + 1

    return [_serialize_group(g, counts.get(g.id, 0)) for g in groups]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_access_group(
    req: AccessGroupCreateRequest,
    current_user: AdminUser = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """Creates a new Access Group."""
    clean_name = req.name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access group name is required.")

    res = await db.execute(select(AccessGroup).where(AccessGroup.name == clean_name))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An access group with this name already exists.",
        )

    clean_tags = [t.strip().lower() for t in (req.tags or []) if t.strip()]
    group = AccessGroup(
        name=clean_name,
        description=req.description.strip() if req.description else None,
        tags_json=json.dumps(clean_tags),
        llm_provider=req.llm_provider.strip().lower() if req.llm_provider else None,
        api_key=req.api_key.strip() if req.api_key else None,
        model_name=req.model_name.strip() if req.model_name else None,
    )
    db.add(group)
    await db.commit()
    await db.refresh(group)

    return _serialize_group(group, 0)


@router.put("/{group_id}")
async def update_access_group(
    group_id: int,
    req: AccessGroupUpdateRequest,
    current_user: AdminUser = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """Updates an existing Access Group."""
    res = await db.execute(select(AccessGroup).where(AccessGroup.id == group_id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found.")

    if req.name is not None:
        clean_name = req.name.strip()
        if not clean_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Access group name cannot be empty.")
        group.name = clean_name
    if req.description is not None:
        group.description = req.description.strip() if req.description else None
    if req.tags is not None:
        clean_tags = [t.strip().lower() for t in req.tags if t.strip()]
        group.tags_json = json.dumps(clean_tags)
    if req.llm_provider is not None:
        group.llm_provider = req.llm_provider.strip().lower() if req.llm_provider else None
    if req.api_key is not None:
        api_key_val = req.api_key.strip()
        if api_key_val and not api_key_val.startswith("••••") and not "••••" in api_key_val:
            group.api_key = api_key_val
        elif api_key_val == "":
            group.api_key = None
    if req.model_name is not None:
        group.model_name = req.model_name.strip() if req.model_name else None

    await db.commit()
    await db.refresh(group)

    return _serialize_group(group)


@router.delete("/{group_id}")
async def delete_access_group(
    group_id: int,
    current_user: AdminUser = Depends(require_admin_role),
    db: AsyncSession = Depends(get_db),
):
    """Deletes an Access Group."""
    res = await db.execute(select(AccessGroup).where(AccessGroup.id == group_id))
    group = res.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found.")

    await db.delete(group)
    await db.commit()
    return {"status": "ok", "message": "Access group deleted."}
