import json
from typing import Optional
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.ai.memory import MemoryManager
from app.ai.orchestrator import AIOrchestrator
from app.flows.engine import FlowEngine
from app.models.config_override import ConfigOverride
from app.schemas.bot_response import BotResponse

router = APIRouter(prefix="/widget", tags=["Website Widget"])

# NOTE: unlike every other inbound surface in this service (signed webhooks),
# /api/v1/widget/* is reachable directly from arbitrary third-party browser JS
# since widget.js is by design embedded in public page source — its endpoint
# URLs are trivially discoverable and there is no per-request auth. Recommend
# adding rate limiting (e.g. slowapi, per session_id + per IP) scoped to this
# router before wide rollout; not added here to avoid introducing a new
# dependency without sign-off.


class WidgetActionRequest(BaseModel):
    action_id: str
    session_id: str
    user_input: Optional[str] = None


class WidgetChatRequest(BaseModel):
    message: str
    session_id: str


@router.post("/chat/stream")
async def widget_chat_stream(req: WidgetChatRequest, db: AsyncSession = Depends(get_db)):
    """Streams the LLM response to the website widget using SSE."""

    async def event_generator():
        stream = AIOrchestrator.process_message_stream(
            db=db,
            channel="widget",
            customer_identifier=req.session_id,
            user_message=req.message,
        )
        async for chunk in stream:
            if isinstance(chunk, str):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            elif isinstance(chunk, dict) and chunk.get("type") == "final":
                yield f"data: {json.dumps({'final': chunk['data'].model_dump()})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/action", response_model=BotResponse)
async def widget_action(req: WidgetActionRequest, db: AsyncSession = Depends(get_db)) -> BotResponse:
    """Dispatches a widget button/product-card click (e.g. cart_add_12, flow_checkout)
    into the same deterministic flow engine every other channel uses."""
    session = await MemoryManager.get_or_create_session(
        db, channel="widget", customer_identifier=req.session_id
    )
    return await FlowEngine.handle_action(
        db=db,
        session=session,
        action_id=req.action_id,
        user_input=req.user_input,
    )


@router.get("/config")
async def widget_config(db: AsyncSession = Depends(get_db)) -> dict:
    """Minimal launcher metadata for the floating widget (business name, welcome message)."""
    stmt = select(ConfigOverride).where(ConfigOverride.key == "business_name")
    res = await db.execute(stmt)
    override = res.scalars().first()
    business_name = override.value if override else settings.APP_NAME

    return {
        "business_name": business_name,
        "welcome_message": f"👋 Hi! How can {business_name} help you today?",
    }
