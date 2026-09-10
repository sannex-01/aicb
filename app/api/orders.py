import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.order import Order, PaymentLog
from app.models.customer import Customer
from app.models.user import AdminUser

router = APIRouter(prefix="/orders", tags=["Orders"])


def _order_summary(o: Order) -> dict:
    try:
        items = json.loads(o.items_json or "[]")
    except Exception:
        items = []
    return {
        "id": o.id,
        "order_reference": o.order_reference,
        "group_reference": o.group_reference,
        "customer_identifier": o.customer_identifier,
        "customer_name": o.customer_name,
        "customer_phone": o.customer_phone,
        "customer_email": o.customer_email,
        "channel": o.channel,
        "status": o.status,
        "fulfillment_status": o.fulfillment_status,
        "total_amount": float(o.total_amount or 0.0),
        "currency": o.currency,
        "items_count": len(items),
        "payment_gateway": o.payment_gateway,
        "checkout_url": o.checkout_url,
        "tracking_url": o.tracking_url,
        "courier_name": o.courier_name,
        "created_at": o.created_at.isoformat() if o.created_at else None,
        "updated_at": o.updated_at.isoformat() if o.updated_at else None,
    }


@router.get("")
async def list_orders(
    customer_id: Optional[int] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    channel: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Lists orders, newest first. Optionally scoped to one customer (matched
    on the loose identifiers captured at checkout — orders have no
    customer_id FK)."""
    stmt = select(Order)

    if status_filter and status_filter.strip():
        stmt = stmt.where(Order.status == status_filter.strip().lower())
    if channel and channel.strip():
        stmt = stmt.where(Order.channel == channel.strip().lower())

    if customer_id is not None:
        cust = (await db.execute(select(Customer).where(Customer.id == customer_id))).scalar_one_or_none()
        if not cust:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
        idents = [v for v in (cust.wa_id, cust.telegram_id, cust.phone_number, cust.email) if v]
        if not idents:
            return []
        stmt = stmt.where(or_(
            Order.customer_identifier.in_(idents),
            Order.customer_phone.in_(idents),
            Order.customer_email.in_(idents),
        ))

    stmt = stmt.order_by(desc(Order.created_at)).limit(limit)
    rows = (await db.execute(stmt)).scalars().all()
    return [_order_summary(o) for o in rows]


@router.get("/{order_id}")
async def get_order_detail(
    order_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Full order detail for the Orders offcanvas: line items, customer,
    fulfillment breakdown, payment logs, and any split-order siblings."""
    o = (await db.execute(select(Order).where(Order.id == order_id))).scalar_one_or_none()
    if not o:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    try:
        items = json.loads(o.items_json or "[]")
    except Exception:
        items = []
    try:
        metadata = json.loads(o.metadata_json or "{}")
    except Exception:
        metadata = {}

    line_items = [
        {
            "item_id": it.get("item_id") or it.get("id"),
            "variant_id": it.get("variant_id"),
            "title": it.get("title") or it.get("name") or f"Item #{it.get('item_id') or it.get('id')}",
            "quantity": int(it.get("quantity", 1) or 1),
            "price": float(it.get("price", 0) or 0),
            "line_total": float(it.get("price", 0) or 0) * int(it.get("quantity", 1) or 1),
            "source": it.get("source"),
            "fulfillment_type": it.get("fulfillment_type"),
        }
        for it in items
    ]

    # Payment attempts for this order reference.
    pay_rows = (await db.execute(
        select(PaymentLog).where(PaymentLog.order_reference == o.order_reference).order_by(desc(PaymentLog.created_at))
    )).scalars().all()
    payments = [
        {
            "id": p.id,
            "gateway": p.gateway,
            "gateway_reference": p.gateway_reference,
            "amount": float(p.amount or 0.0),
            "currency": p.currency,
            "status": p.status,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in pay_rows
    ]

    # Sibling orders from a split checkout (shared group_reference).
    siblings = []
    if o.group_reference:
        sib_rows = (await db.execute(
            select(Order).where(Order.group_reference == o.group_reference, Order.id != o.id).order_by(Order.created_at)
        )).scalars().all()
        siblings = [_order_summary(s) for s in sib_rows]

    # Best-effort link to the customer record.
    customer = None
    match_vals = [v for v in (o.customer_identifier, o.customer_phone, o.customer_email) if v]
    if match_vals:
        c = (await db.execute(select(Customer).where(or_(
            Customer.wa_id.in_(match_vals),
            Customer.telegram_id.in_(match_vals),
            Customer.phone_number.in_(match_vals),
            Customer.email.in_(match_vals),
        )))).scalars().first()
        if c:
            customer = {
                "id": c.id,
                "name": c.name or "Unnamed Customer",
                "phone_number": c.phone_number,
                "email": c.email,
                "wa_id": c.wa_id,
                "telegram_id": c.telegram_id,
            }

    return {
        "order": {
            **_order_summary(o),
            "shipping_address": o.shipping_address,
            "payment_reference": o.payment_reference,
        },
        "line_items": line_items,
        "customer": customer,
        "payments": payments,
        "fulfillment": {
            "status": o.fulfillment_status or "pending",
            "tracking_url": o.tracking_url,
            "courier_name": o.courier_name,
            "groups": metadata.get("fulfillment_groups", {}),
        },
        "siblings": siblings,
        "metadata": metadata,
    }
