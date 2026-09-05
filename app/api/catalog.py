import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user, require_admin_role
from app.models.catalog import CatalogItem
from app.models.access_group import AccessGroup
from app.models.user import AdminUser
from app.core.access import parse_tags_json, parse_ids_json

router = APIRouter(prefix="/admin/catalog", tags=["Admin Catalog Management"])


class CatalogItemCreateRequest(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    currency: str = "NGN"
    category: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: bool = True
    stock_quantity: int = 100
    access_group_ids: Optional[List[int]] = []
    access_tags: Optional[List[str]] = []


class CatalogItemUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None
    access_group_ids: Optional[List[int]] = None
    access_tags: Optional[List[str]] = None


def _serialize_catalog_item(itm: CatalogItem, groups_map: Optional[dict] = None) -> dict:
    group_ids = parse_ids_json(getattr(itm, "access_group_ids_json", "[]"))
    tags = parse_tags_json(itm.access_tags_json)
    
    group_names = []
    if groups_map:
        for gid in group_ids:
            if gid in groups_map:
                group_names.append(groups_map[gid])

    return {
        "id": itm.id,
        "source": itm.source,
        "external_id": itm.external_id,
        "title": itm.title,
        "description": itm.description,
        "price": itm.price,
        "currency": itm.currency,
        "category": itm.category,
        "image_url": itm.image_url,
        "in_stock": itm.in_stock,
        "stock_quantity": itm.stock_quantity,
        "access_group_ids": group_ids,
        "access_group_names": group_names,
        "access_tags": tags,
        "is_global": not bool(group_ids or tags),
        "created_at": itm.created_at.isoformat() if itm.created_at else None,
    }


@router.get("")
async def list_admin_catalog(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Lists catalog items with search and access tags / group scopes."""
    stmt = select(CatalogItem)
    conditions = []

    if search:
        term = f"%{search.strip()}%"
        conditions.append(or_(CatalogItem.title.ilike(term), CatalogItem.description.ilike(term)))
    if category:
        conditions.append(CatalogItem.category.ilike(f"%{category.strip()}%"))

    if conditions:
        stmt = stmt.where(*conditions)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    offset = (page - 1) * limit
    stmt = stmt.order_by(desc(CatalogItem.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    items = res.scalars().all()

    # Fetch access groups map
    grp_res = await db.execute(select(AccessGroup))
    groups_map = {g.id: g.name for g in grp_res.scalars().all()}

    return {
        "items": [_serialize_catalog_item(itm, groups_map) for itm in items],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_catalog_item(
    req: CatalogItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_admin_role),
):
    """Creates a new catalog product with access group assignments."""
    group_ids = [int(gid) for gid in (req.access_group_ids or []) if gid]
    tags_clean = [t.strip().lower() for t in (req.access_tags or []) if t.strip()]

    # If group_ids are provided, also record group IDs in tags for dual-query compatibility
    combined_tags = list(set(tags_clean + [str(gid) for gid in group_ids]))

    item = CatalogItem(
        source="local",
        title=req.title.strip(),
        description=req.description.strip() if req.description else None,
        price=req.price,
        currency=req.currency.strip().upper(),
        category=req.category.strip() if req.category else None,
        image_url=req.image_url.strip() if req.image_url else None,
        in_stock=req.in_stock,
        stock_quantity=req.stock_quantity,
        access_group_ids_json=json.dumps(group_ids),
        access_tags_json=json.dumps(combined_tags),
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return _serialize_catalog_item(item)


@router.get("/{item_id}")
async def get_catalog_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    stmt = select(CatalogItem).where(CatalogItem.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")

    grp_res = await db.execute(select(AccessGroup))
    groups_map = {g.id: g.name for g in grp_res.scalars().all()}

    return _serialize_catalog_item(item, groups_map)


@router.put("/{item_id}")
async def update_catalog_item(
    item_id: int,
    req: CatalogItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_admin_role),
):
    stmt = select(CatalogItem).where(CatalogItem.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")

    if req.title is not None:
        item.title = req.title.strip()
    if req.description is not None:
        item.description = req.description.strip() if req.description else None
    if req.price is not None:
        item.price = req.price
    if req.currency is not None:
        item.currency = req.currency.strip().upper()
    if req.category is not None:
        item.category = req.category.strip() if req.category else None
    if req.image_url is not None:
        item.image_url = req.image_url.strip() if req.image_url else None
    if req.in_stock is not None:
        item.in_stock = req.in_stock
    if req.stock_quantity is not None:
        item.stock_quantity = req.stock_quantity
    
    if req.access_group_ids is not None:
        group_ids = [int(gid) for gid in req.access_group_ids if gid]
        item.access_group_ids_json = json.dumps(group_ids)
        tags_clean = [t.strip().lower() for t in (req.access_tags or parse_tags_json(item.access_tags_json)) if t.strip() and not t.isdigit()]
        combined_tags = list(set(tags_clean + [str(gid) for gid in group_ids]))
        item.access_tags_json = json.dumps(combined_tags)
    elif req.access_tags is not None:
        tags_clean = [t.strip().lower() for t in req.access_tags if t.strip()]
        item.access_tags_json = json.dumps(tags_clean)

    await db.commit()
    await db.refresh(item)

    return {"status": "ok", "message": "Catalog item updated successfully"}


@router.delete("/{item_id}")
async def delete_catalog_item(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin_role),
):
    stmt = select(CatalogItem).where(CatalogItem.id == item_id)
    res = await db.execute(stmt)
    item = res.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Catalog item not found")

    await db.delete(item)
    await db.commit()

    return {"status": "ok", "message": "Catalog item deleted"}
