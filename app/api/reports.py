"""
Commerce & AI Analytics Reporting API
Provides aggregated analytics on GMV, order conversion, AI resolution efficiency, and channel distribution.
"""

import io
import csv
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_admin_user
from app.models.user import AdminUser
from app.models.order import Order
from app.models.session import ConversationSession
from app.models.catalog import CatalogItem
from app.models.agent import Agent


router = APIRouter(prefix="/reports", tags=["Reports & Analytics"])


class ChannelMetric(BaseModel):
    channel: str
    conversations_count: int
    orders_count: int
    revenue: float
    percentage: float


class ProductPerformance(BaseModel):
    id: int
    name: str
    price: float
    currency: str
    orders_count: int
    total_sales: float


class ReportsSummaryResponse(BaseModel):
    timeframe: str
    total_revenue: float
    total_orders: int
    paid_orders: int
    pending_orders: int
    conversion_rate: float
    average_order_value: float
    total_conversations: int
    ai_resolved_conversations: int
    human_escalated_conversations: int
    ai_resolution_rate: float
    channels: List[ChannelMetric]
    top_products: List[ProductPerformance]
    currency: str


@router.get("/summary", response_model=ReportsSummaryResponse)
async def get_reports_summary(
    days: int = Query(7, description="Number of days to analyze (0 for all time)", ge=0, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin_user),
):

    """Aggregate commerce and AI performance metrics over the requested timeframe."""
    now = datetime.now(timezone.utc)
    since_date = (now - timedelta(days=days)) if days > 0 else None

    # 1. Fetch Orders
    order_stmt = select(Order)
    if since_date:
        order_stmt = order_stmt.where(Order.created_at >= since_date)
    orders_result = await db.scalars(order_stmt)
    orders = orders_result.all()

    total_orders = len(orders)
    paid_orders = [o for o in orders if o.status == "paid"]
    pending_orders = [o for o in orders if o.status in ["pending", "created"]]
    
    total_revenue = sum(o.total_amount for o in paid_orders if o.total_amount)
    paid_count = len(paid_orders)
    conversion_rate = round((paid_count / total_orders * 100), 1) if total_orders > 0 else 0.0
    average_order_value = round((total_revenue / paid_count), 2) if paid_count > 0 else 0.0

    primary_currency = paid_orders[0].currency if paid_orders and paid_orders[0].currency else "NGN"

    # 2. Fetch Conversations
    conv_stmt = select(ConversationSession)
    if since_date:
        conv_stmt = conv_stmt.where(ConversationSession.created_at >= since_date)
    conv_result = await db.scalars(conv_stmt)
    conversations = conv_result.all()

    total_conversations = len(conversations)
    # Human escalation occurs if assigned to human or state has escalation flag
    escalated_convs = [c for c in conversations if getattr(c, "assigned_human_id", None) or "escalat" in str(getattr(c, "current_intent", "")).lower()]
    escalated_count = len(escalated_convs)
    ai_resolved_count = max(0, total_conversations - escalated_count)
    ai_resolution_rate = round((ai_resolved_count / total_conversations * 100), 1) if total_conversations > 0 else 100.0

    # 3. Channel breakdown
    channels_map = {"whatsapp": 0, "telegram": 0, "widget": 0}
    channel_revenue = {"whatsapp": 0.0, "telegram": 0.0, "widget": 0.0}
    channel_orders = {"whatsapp": 0, "telegram": 0, "widget": 0}

    for c in conversations:
        ch = (c.channel or "widget").lower()
        if ch in channels_map:
            channels_map[ch] += 1
        else:
            channels_map[ch] = 1
            channel_revenue[ch] = 0.0
            channel_orders[ch] = 0

    for o in orders:
        ch = (o.channel or "widget").lower()
        if ch not in channel_orders:
            channel_orders[ch] = 0
            channel_revenue[ch] = 0.0
        channel_orders[ch] += 1
        if o.status == "paid":
            channel_revenue[ch] += (o.total_amount or 0.0)

    total_channel_activity = sum(channels_map.values()) or 1
    channels_list: List[ChannelMetric] = []
    for ch_name, conv_cnt in channels_map.items():
        channels_list.append(
            ChannelMetric(
                channel=ch_name.capitalize(),
                conversations_count=conv_cnt,
                orders_count=channel_orders.get(ch_name, 0),
                revenue=round(channel_revenue.get(ch_name, 0.0), 2),
                percentage=round((conv_cnt / total_channel_activity) * 100, 1),
            )
        )

    # 4. Top Products
    products_stmt = select(CatalogItem).where(CatalogItem.in_stock == True).limit(5)
    products_res = await db.scalars(products_stmt)
    products = products_res.all()

    top_products: List[ProductPerformance] = []
    for p in products:
        # Match orders containing product title
        matched_orders = [o for o in paid_orders if (p.title or "").lower() in str(getattr(o, "items_json", "")).lower()]
        orders_cnt = len(matched_orders) or 1
        top_products.append(
            ProductPerformance(
                id=p.id,
                name=p.title or f"Product #{p.id}",
                price=p.price or 0.0,
                currency=p.currency or "NGN",
                orders_count=orders_cnt,
                total_sales=round((p.price or 0.0) * orders_cnt, 2),
            )
        )

    top_products.sort(key=lambda x: x.total_sales, reverse=True)

    return ReportsSummaryResponse(
        timeframe=f"{days}d" if days > 0 else "all",
        total_revenue=round(total_revenue, 2),
        total_orders=total_orders,
        paid_orders=paid_count,
        pending_orders=len(pending_orders),
        conversion_rate=conversion_rate,
        average_order_value=average_order_value,
        total_conversations=total_conversations,
        ai_resolved_conversations=ai_resolved_count,
        human_escalated_conversations=escalated_count,
        ai_resolution_rate=ai_resolution_rate,
        channels=channels_list,
        top_products=top_products,
        currency=primary_currency,
    )


@router.get("/export-csv")
async def export_reports_csv(
    days: int = Query(30, description="Timeframe in days", ge=0, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: AdminUser = Depends(get_current_admin_user),
):

    """Export orders and sales analytics report as CSV."""
    now = datetime.now(timezone.utc)
    since_date = (now - timedelta(days=days)) if days > 0 else None

    stmt = select(Order).order_by(desc(Order.id))
    if since_date:
        stmt = stmt.where(Order.created_at >= since_date)
    res = await db.scalars(stmt)
    orders = res.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Reference", "Customer Name", "Customer Phone", 
        "Amount", "Currency", "Status", "Channel", "Payment Provider", "Created At"
    ])

    for o in orders:
        writer.writerow([
            o.id,
            getattr(o, "reference", "") or getattr(o, "id", ""),
            getattr(o, "customer_name", "Anonymous"),
            getattr(o, "customer_phone", "") or getattr(o, "customer_id", ""),
            o.total_amount or 0.0,
            o.currency or "NGN",
            o.status,
            o.channel or "Widget",
            getattr(o, "payment_provider", "paystack"),
            o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "",
        ])

    output.seek(0)
    filename = f"aicb_commerce_report_{datetime.now().strftime('%Y%m%d')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
