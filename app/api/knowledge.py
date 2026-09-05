import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user, require_admin_role
from app.models.knowledge import KnowledgeDoc
from app.models.user import AdminUser
from app.core.access import parse_tags_json

router = APIRouter(prefix="/admin/knowledge", tags=["Admin Knowledge Base Management"])


class KnowledgeDocCreateRequest(BaseModel):
    title: str
    category: Optional[str] = None
    content: str
    tags: Optional[str] = None
    access_tags: List[str] = []


class KnowledgeDocUpdateRequest(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[str] = None
    access_tags: Optional[List[str]] = None


@router.get("")
async def list_admin_knowledge(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Lists knowledge base documents with access tags and categories."""
    stmt = select(KnowledgeDoc)
    conditions = []

    if search:
        term = f"%{search.strip()}%"
        conditions.append(or_(KnowledgeDoc.title.ilike(term), KnowledgeDoc.content.ilike(term)))
    if category:
        conditions.append(KnowledgeDoc.category.ilike(f"%{category.strip()}%"))

    if conditions:
        stmt = stmt.where(*conditions)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    offset = (page - 1) * limit
    stmt = stmt.order_by(desc(KnowledgeDoc.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    docs = res.scalars().all()

    return {
        "items": [
            {
                "id": doc.id,
                "title": doc.title,
                "category": doc.category or "General",
                "content": doc.content,
                "tags": doc.tags,
                "access_tags": parse_tags_json(doc.access_tags_json),
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
            }
            for doc in docs
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_knowledge_doc(
    req: KnowledgeDocCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_admin_role),
):
    """Creates a new knowledge document with access tags."""
    tags_clean = [t.strip().lower() for t in req.access_tags if t.strip()]

    doc = KnowledgeDoc(
        title=req.title,
        category=req.category,
        content=req.content,
        tags=req.tags,
        access_tags_json=json.dumps(tags_clean),
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category,
        "access_tags": tags_clean,
    }


@router.get("/{doc_id}")
async def get_knowledge_doc(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    stmt = select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    return {
        "id": doc.id,
        "title": doc.title,
        "category": doc.category or "General",
        "content": doc.content,
        "tags": doc.tags,
        "access_tags": parse_tags_json(doc.access_tags_json),
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.put("/{doc_id}")
async def update_knowledge_doc(
    doc_id: int,
    req: KnowledgeDocUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_admin_role),
):
    stmt = select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    if req.title is not None:
        doc.title = req.title
    if req.category is not None:
        doc.category = req.category
    if req.content is not None:
        doc.content = req.content
    if req.tags is not None:
        doc.tags = req.tags
    if req.access_tags is not None:
        tags_clean = [t.strip().lower() for t in req.access_tags if t.strip()]
        doc.access_tags_json = json.dumps(tags_clean)

    await db.commit()
    await db.refresh(doc)

    return {"status": "ok", "message": "Knowledge document updated successfully"}


@router.delete("/{doc_id}")
async def delete_knowledge_doc(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin_role),
):
    stmt = select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id)
    res = await db.execute(stmt)
    doc = res.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Knowledge document not found")

    await db.delete(doc)
    await db.commit()

    return {"status": "ok", "message": "Knowledge document deleted"}
