from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.session import ConversationSession, MessageLog
from app.models.customer import Customer
from app.models.agent import Agent
from app.models.user import AdminUser

router = APIRouter(prefix="/conversations", tags=["Conversations Viewer"])

@router.get("")
async def list_conversations(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    channel: Optional[str] = Query(None, description="Filter by channel: whatsapp, telegram, widget"),
    agent_id: Optional[int] = Query(None, description="Filter by agent ID"),
    search: Optional[str] = Query(None, description="Search customer name, phone, email, or identifier"),
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Returns paginated list of conversation sessions across all customers with optional filtering."""
    stmt = select(ConversationSession)

    if channel and channel.strip():
        stmt = stmt.where(ConversationSession.channel == channel.strip().lower())

    if agent_id:
        stmt = stmt.where(ConversationSession.agent_id == agent_id)

    if search and search.strip():
        term = f"%{search.strip()}%"
        customer_matches_stmt = select(Customer).where(
            or_(
                Customer.name.ilike(term),
                Customer.phone_number.ilike(term),
                Customer.email.ilike(term),
                Customer.wa_id.ilike(term),
                Customer.telegram_id.ilike(term),
            )
        )
        matching_cust_res = await db.execute(customer_matches_stmt)
        matching_custs = matching_cust_res.scalars().all()

        matching_identifiers = set()
        for c in matching_custs:
            if c.wa_id: matching_identifiers.add(c.wa_id)
            if c.telegram_id: matching_identifiers.add(c.telegram_id)
            if c.phone_number: matching_identifiers.add(c.phone_number)

        if matching_identifiers:
            stmt = stmt.where(
                or_(
                    ConversationSession.customer_identifier.ilike(term),
                    ConversationSession.customer_identifier.in_(list(matching_identifiers))
                )
            )
        else:
            stmt = stmt.where(ConversationSession.customer_identifier.ilike(term))

    offset = (page - 1) * limit
    stmt = stmt.order_by(desc(ConversationSession.last_active_at)).offset(offset).limit(limit)
    res = await db.execute(stmt)
    sessions = res.scalars().all()

    # Try to map to customers
    items = []
    for s in sessions:
        customer_stmt = select(Customer).where(
            or_(
                Customer.wa_id == s.customer_identifier,
                Customer.telegram_id == s.customer_identifier,
                Customer.phone_number == s.customer_identifier
            )
        ).limit(1)
        cust_res = await db.execute(customer_stmt)
        customer = cust_res.scalar_one_or_none()

        items.append({
            "id": s.id,
            "session_key": s.session_key,
            "channel": s.channel,
            "customer_identifier": s.customer_identifier,
            "agent_id": s.agent_id,
            "agent": {
                "id": s.agent.id,
                "name": s.agent.name,
                "slug": s.agent.slug,
            } if getattr(s, "agent", None) else None,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
            "customer": {
                "id": customer.id,
                "name": customer.name,
                "email": customer.email,
                "phone_number": customer.phone_number,
            } if customer else None
        })

    return {
        "items": items,
        "page": page,
        "limit": limit
    }

@router.get("/{session_id}")
async def get_conversation_thread(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
):
    """Returns the full message history for a specific conversation session."""
    stmt = select(ConversationSession).where(ConversationSession.id == session_id)
    res = await db.execute(stmt)
    session = res.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    # Look up customer
    customer_stmt = select(Customer).where(
        or_(
            Customer.wa_id == session.customer_identifier,
            Customer.telegram_id == session.customer_identifier,
            Customer.phone_number == session.customer_identifier
        )
    ).limit(1)
    cust_res = await db.execute(customer_stmt)
    customer = cust_res.scalar_one_or_none()

    msg_stmt = select(MessageLog).where(MessageLog.session_id == session.id).order_by(MessageLog.created_at.asc())
    msg_res = await db.execute(msg_stmt)
    msgs = msg_res.scalars().all()

    return {
        "id": session.id,
        "session_key": session.session_key,
        "channel": session.channel,
        "customer_identifier": session.customer_identifier,
        "agent_id": session.agent_id,
        "agent": {
            "id": session.agent.id,
            "name": session.agent.name,
            "slug": session.agent.slug,
        } if getattr(session, "agent", None) else None,
        "bot_mode": session.bot_mode,
        "active_flow": session.active_flow,
        "current_step": session.current_step,
        "last_active_at": session.last_active_at.isoformat() if session.last_active_at else None,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "email": customer.email,
            "phone_number": customer.phone_number,
        } if customer else None,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            } for m in msgs
        ]
    }
