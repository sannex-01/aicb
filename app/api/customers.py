import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, or_, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user, require_admin_role, require_operator_or_above
from app.models.customer import Customer
from app.models.order import Order
from app.models.session import ConversationSession
from app.models.user import AdminUser

router = APIRouter(prefix="/customers", tags=["Customers Management"])

_PAID_STATUSES = ("paid", "processing", "completed")


def _order_identifiers(c: Customer) -> set[str]:
    """Every value an Order row might carry that identifies this customer.
    Orders have no customer_id FK — they're matched loosely on the channel
    identifier / phone / email captured at checkout."""
    vals = set()
    for v in (c.wa_id, c.telegram_id, c.phone_number, c.email):
        if v:
            vals.add(v.strip().lower())
    return vals


def _order_matches_customer(o: Order, idents: set[str]) -> bool:
    for v in (o.customer_identifier, o.customer_phone, o.customer_email):
        if v and v.strip().lower() in idents:
            return True
    return False


def _live_order_stats(orders: list[Order]) -> tuple[int, float]:
    """(order count, amount spent on paid/processing/completed orders)."""
    spent = sum(float(o.total_amount or 0.0) for o in orders if (o.status or "") in _PAID_STATUSES)
    return len(orders), spent


class CustomerUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None
    notes: Optional[str] = None


@router.get("")
async def list_customers(
    search: Optional[str] = Query(None, description="Search by name, email, phone, or channel ID"),
    channel: Optional[str] = Query(None, description="Filter by channel: whatsapp or telegram"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Returns paginated list of customers with order counts and spent totals."""
    stmt = select(Customer)

    conditions = []
    if search:
        term = f"%{search.strip()}%"
        conditions.append(
            or_(
                Customer.name.ilike(term),
                Customer.email.ilike(term),
                Customer.phone_number.ilike(term),
                Customer.wa_id.ilike(term),
                Customer.telegram_id.ilike(term),
            )
        )

    if channel == "whatsapp":
        conditions.append(Customer.wa_id.is_not(None))
    elif channel == "telegram":
        conditions.append(Customer.telegram_id.is_not(None))

    if conditions:
        stmt = stmt.where(*conditions)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_res = await db.execute(count_stmt)
    total = total_res.scalar() or 0

    # Paginate
    offset = (page - 1) * limit
    stmt = stmt.order_by(desc(Customer.last_seen_at), desc(Customer.created_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    customers = res.scalars().all()

    # Order counts / spend are computed live from the orders table rather
    # than read from customers.total_orders / total_spent, which are never
    # maintained anywhere and so are always stale (usually 0). One query for
    # all orders on this page, matched in Python on the loose identifiers.
    all_orders_res = await db.execute(select(Order))
    all_orders = list(all_orders_res.scalars().all())

    items = []
    for c in customers:
        channels = []
        if c.wa_id:
            channels.append("whatsapp")
        if c.telegram_id:
            channels.append("telegram")

        idents = _order_identifiers(c)
        cust_orders = [o for o in all_orders if idents and _order_matches_customer(o, idents)]
        order_count, spent = _live_order_stats(cust_orders)

        items.append({
            "id": c.id,
            "name": c.name or "Unnamed Customer",
            "email": c.email,
            "phone_number": c.phone_number,
            "wa_id": c.wa_id,
            "telegram_id": c.telegram_id,
            "channels": channels,
            "total_orders": order_count,
            "total_spent": spent,
            "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.get("/{customer_id}")
async def get_customer_details(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Retrieves the customer profile, live order history, and a lightweight
    conversation summary (no message transcripts — those are viewed on the
    Conversations page)."""
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    customer = res.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    idents = _order_identifiers(customer)

    orders = []
    order_rows: list[Order] = []
    if idents:
        order_res = await db.execute(select(Order).order_by(desc(Order.created_at)))
        order_rows = [o for o in order_res.scalars().all() if _order_matches_customer(o, idents)]
        for o in order_rows[:50]:
            orders.append({
                "id": o.id,
                "order_reference": o.order_reference,
                "total_amount": float(o.total_amount or 0.0),
                "currency": o.currency,
                "status": o.status,
                "fulfillment_status": o.fulfillment_status,
                "channel": o.channel,
                "items_count": len(json.loads(o.items_json)) if o.items_json else 0,
                "checkout_url": o.checkout_url,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

    order_count, spent = _live_order_stats(order_rows)

    # Conversation summary only — count of sessions + last activity, so the
    # offcanvas can link to the full transcripts on the Conversations page.
    session_ids = [v for v in (customer.wa_id, customer.telegram_id, customer.phone_number) if v]
    session_count = 0
    last_conversation_at = None
    if session_ids:
        sess_res = await db.execute(
            select(ConversationSession)
            .where(ConversationSession.customer_identifier.in_(session_ids))
            .order_by(desc(ConversationSession.last_active_at))
        )
        sess_rows = sess_res.scalars().all()
        session_count = len(sess_rows)
        if sess_rows and sess_rows[0].last_active_at:
            last_conversation_at = sess_rows[0].last_active_at.isoformat()

    channels = []
    if customer.wa_id:
        channels.append("whatsapp")
    if customer.telegram_id:
        channels.append("telegram")

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name or "Unnamed Customer",
            "email": customer.email,
            "phone_number": customer.phone_number,
            "wa_id": customer.wa_id,
            "telegram_id": customer.telegram_id,
            "channels": channels,
            "total_orders": order_count,
            "total_spent": spent,
            "last_seen_at": customer.last_seen_at.isoformat() if customer.last_seen_at else None,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "metadata": json.loads(customer.metadata_json or "{}"),
        },
        "orders": orders,
        "conversation_summary": {
            "session_count": session_count,
            "last_conversation_at": last_conversation_at,
            # The term the Conversations page search matches on.
            "search_term": customer.phone_number or customer.email or customer.name or customer.wa_id or customer.telegram_id or "",
        },
    }


@router.put("/{customer_id}")
async def update_customer(
    customer_id: int,
    req: CustomerUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(require_operator_or_above),
):
    """Updates customer contact details and notes."""
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    customer = res.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    if req.name is not None:
        customer.name = req.name
    if req.email is not None:
        customer.email = req.email
    if req.phone_number is not None:
        customer.phone_number = req.phone_number
    if req.notes is not None:
        try:
            meta = json.loads(customer.metadata_json or "{}")
        except Exception:
            meta = {}
        meta["notes"] = req.notes
        customer.metadata_json = json.dumps(meta)

    await db.commit()
    await db.refresh(customer)

    return {"status": "ok", "message": "Customer updated successfully"}


@router.delete("/{customer_id}")
async def delete_customer(
    customer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(require_admin_role),
):
    """Deletes customer record for GDPR/privacy erasure."""
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    customer = res.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    await db.delete(customer)
    await db.commit()

    return {"status": "ok", "message": "Customer deleted successfully"}
