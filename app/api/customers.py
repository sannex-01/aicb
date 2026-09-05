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
from app.models.session import ConversationSession, MessageLog
from app.models.user import AdminUser

router = APIRouter(prefix="/customers", tags=["Customers Management"])


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

    items = []
    for c in customers:
        channels = []
        if c.wa_id:
            channels.append("whatsapp")
        if c.telegram_id:
            channels.append("telegram")

        items.append({
            "id": c.id,
            "name": c.name or "Unnamed Customer",
            "email": c.email,
            "phone_number": c.phone_number,
            "wa_id": c.wa_id,
            "telegram_id": c.telegram_id,
            "channels": channels,
            "total_orders": c.total_orders or 0,
            "total_spent": float(c.total_spent or 0.0),
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
    """Retrieves full customer profile, order history, and recent chat transcripts."""
    stmt = select(Customer).where(Customer.id == customer_id)
    res = await db.execute(stmt)
    customer = res.scalar_one_or_none()

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Fetch orders associated with customer
    identifiers = [id_val for id_val in [customer.wa_id, customer.telegram_id, customer.phone_number] if id_val]
    order_conditions = []
    if identifiers:
        order_conditions.append(Order.customer_identifier.in_(identifiers))
    if customer.email:
        order_conditions.append(Order.customer_email == customer.email)
    if customer.phone_number:
        order_conditions.append(Order.customer_phone == customer.phone_number)

    orders = []
    if order_conditions:
        order_stmt = select(Order).where(or_(*order_conditions)).order_by(desc(Order.created_at)).limit(20)
        order_res = await db.execute(order_stmt)
        for o in order_res.scalars().all():
            orders.append({
                "id": o.id,
                "order_reference": o.order_reference,
                "total_amount": o.total_amount,
                "currency": o.currency,
                "status": o.status,
                "channel": o.channel,
                "items_count": len(json.loads(o.items_json)) if o.items_json else 0,
                "checkout_url": o.checkout_url,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            })

    # Fetch recent conversation sessions & messages
    session_conditions = []
    if customer.wa_id:
        session_conditions.append(ConversationSession.customer_identifier == customer.wa_id)
    if customer.telegram_id:
        session_conditions.append(ConversationSession.customer_identifier == customer.telegram_id)
    if customer.phone_number:
        session_conditions.append(ConversationSession.customer_identifier == customer.phone_number)

    recent_sessions = []
    if session_conditions:
        sess_stmt = select(ConversationSession).where(or_(*session_conditions)).order_by(desc(ConversationSession.last_active_at)).limit(5)
        sess_res = await db.execute(sess_stmt)
        session_rows = sess_res.scalars().all()

        for s in session_rows:
            # Fetch message logs
            msg_stmt = select(MessageLog).where(MessageLog.session_id == s.id).order_by(MessageLog.created_at.asc()).limit(50)
            msg_res = await db.execute(msg_stmt)
            msgs = msg_res.scalars().all()

            recent_sessions.append({
                "session_id": s.id,
                "session_key": s.session_key,
                "channel": s.channel,
                "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
                "messages": [
                    {
                        "id": m.id,
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in msgs
                ],
            })

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
            "total_orders": customer.total_orders or len(orders),
            "total_spent": float(customer.total_spent or sum(o["total_amount"] for o in orders if o["status"] in ("paid", "completed"))),
            "last_seen_at": customer.last_seen_at.isoformat() if customer.last_seen_at else None,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "metadata": json.loads(customer.metadata_json or "{}"),
        },
        "orders": orders,
        "sessions": recent_sessions,
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
