import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.catalog import CatalogItem
from app.models.order import Order
from app.ai.orchestrator import AIOrchestrator

router = APIRouter(prefix="/miniapp", tags=["Mini App"])


class ChatRequest(BaseModel):
    message: str
    user_id: str
    first_name: str = "Guest"


@router.get("/catalog")
async def get_catalog(db: AsyncSession = Depends(get_db)):
    """Returns catalog items for the Mini App."""
    stmt = select(CatalogItem).limit(100)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.get("/orders/{user_id}")
async def get_orders(user_id: str, db: AsyncSession = Depends(get_db)):
    """Returns orders for a specific user."""
    stmt = select(Order).where(Order.customer_identifier == user_id).order_by(Order.created_at.desc()).limit(50)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.post("/chat/stream")
async def stream_chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """Streams the LLM response to the Mini App using SSE."""

    async def event_generator():
        stream = AIOrchestrator.process_message_stream(
            db=db,
            channel="miniapp",
            customer_identifier=req.user_id,
            user_message=req.message,
            customer_name=req.first_name,
        )
        async for chunk in stream:
            if isinstance(chunk, str):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            elif isinstance(chunk, dict) and chunk.get("type") == "final":
                yield f"data: {json.dumps({'final': chunk['data'].model_dump()})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
