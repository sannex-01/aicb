import json
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.security import get_current_admin_user
from app.models.business import BusinessProfile
from app.models.agent import Agent
from app.models.customer import Customer
from app.models.order import Order
from app.models.session import ConversationSession
from app.models.catalog import CatalogItem
from app.models.knowledge import KnowledgeDoc
from app.models.user import AdminUser

router = APIRouter(prefix="/overview", tags=["Overview Dashboard"])


@router.get("")
async def get_overview_stats(
    db: AsyncSession = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Aggregates system-wide operational metrics for the Standalone Admin Dashboard."""
    # 1. Business Profile
    biz_stmt = select(BusinessProfile).limit(1)
    biz_res = await db.execute(biz_stmt)
    biz = biz_res.scalar_one_or_none()

    business_name = biz.name if biz else settings.APP_NAME
    currency = biz.currency if biz else "NGN"

    # 2. Total Agents
    agent_stmt = select(func.count(Agent.id))
    agent_res = await db.execute(agent_stmt)
    total_agents = agent_res.scalar() or 0

    active_agent_stmt = select(func.count(Agent.id)).where(Agent.is_active == True)
    active_agent_res = await db.execute(active_agent_stmt)
    active_agents = active_agent_res.scalar() or 0

    # 3. Total Customers
    cust_stmt = select(func.count(Customer.id))
    cust_res = await db.execute(cust_stmt)
    total_customers = cust_res.scalar() or 0

    # 4. Total Products & Knowledge Docs
    prod_stmt = select(func.count(CatalogItem.id))
    prod_res = await db.execute(prod_stmt)
    total_products = prod_res.scalar() or 0

    doc_stmt = select(func.count(KnowledgeDoc.id))
    doc_res = await db.execute(doc_stmt)
    total_docs = doc_res.scalar() or 0

    # 5. Orders and Revenue
    order_stmt = select(func.count(Order.id))
    order_res = await db.execute(order_stmt)
    total_orders = order_res.scalar() or 0

    revenue_stmt = select(func.sum(Order.total_amount)).where(
        Order.status.in_(["paid", "processing", "completed"])
    )
    rev_res = await db.execute(revenue_stmt)
    total_revenue = float(rev_res.scalar() or 0.0)

    # 6. Active Conversations (Sessions active in the last 7 days)
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    session_stmt = select(func.count(ConversationSession.id)).where(
        ConversationSession.last_active_at >= cutoff
    )
    sess_res = await db.execute(session_stmt)
    active_sessions_7d = sess_res.scalar() or 0

    # 7. Recent Orders
    recent_orders_stmt = select(Order).order_by(desc(Order.created_at)).limit(5)
    recent_orders_res = await db.execute(recent_orders_stmt)
    recent_orders_data = []
    for o in recent_orders_res.scalars().all():
        recent_orders_data.append({
            "id": o.id,
            "order_reference": o.order_reference,
            "customer_name": o.customer_name or o.customer_identifier or "Customer",
            "channel": o.channel,
            "total_amount": o.total_amount,
            "currency": o.currency,
            "status": o.status,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        })

    # 8. Recent Conversation Sessions
    recent_sessions_stmt = select(ConversationSession).order_by(desc(ConversationSession.last_active_at)).limit(5)
    recent_sessions_res = await db.execute(recent_sessions_stmt)
    recent_sessions_data = []
    for s in recent_sessions_res.scalars().all():
        recent_sessions_data.append({
            "id": s.id,
            "channel": s.channel,
            "customer_identifier": s.customer_identifier,
            "active_flow": s.active_flow,
            "last_active_at": s.last_active_at.isoformat() if s.last_active_at else None,
        })

    return {
        "business": {
            "name": business_name,
            "currency": currency,
            "is_configured": biz.is_configured if biz else False,
            "logo_url": biz.logo_url if biz else None,
        },
        "stats": {
            "total_agents": total_agents,
            "active_agents": active_agents,
            "total_customers": total_customers,
            "total_products": total_products,
            "total_docs": total_docs,
            "total_orders": total_orders,
            "total_revenue": total_revenue,
            "active_sessions_7d": active_sessions_7d,
        },
        "recent_orders": recent_orders_data,
        "recent_sessions": recent_sessions_data,
    }
