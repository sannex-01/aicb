import json
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.ai.memory import MemoryManager
from app.ai.orchestrator import AIOrchestrator
from app.flows.engine import FlowEngine
from app.models.config_override import ConfigOverride
from app.schemas.bot_response import BotResponse

router = APIRouter(prefix="/widget", tags=["Website Widget"])

# NOTE: unlike every other inbound surface in this service (signed webhooks),
# /api/v1/widget/* is reachable directly from arbitrary third-party browser JS
# since widget.js is by design embedded in public page source — its endpoint
# URLs are trivially discoverable and there is no per-request auth. Rate
# limited below (per client IP — session_id is client-supplied and trivially
# spoofable) via slowapi; chat/stream is limited tighter since it costs a
# real LLM call.


class WidgetActionRequest(BaseModel):
    action_id: str
    session_id: str
    user_input: Optional[str] = None


class WidgetChatRequest(BaseModel):
    message: str
    session_id: str


class WidgetProfileRequest(BaseModel):
    session_id: str
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    skipped: bool = False


@router.post("/profile")
@limiter.limit("10/minute")
async def widget_submit_profile(request: Request, req: WidgetProfileRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """One-shot submission of the autofill-friendly form shown immediately on
    panel open (see widget/src/profile-form.ts) — collected fresh every
    session, never persisted as a Customer row (widget has no durable
    identity). 'skipped' stores an empty profile so checkout falls back to
    the same turn-by-turn chat collection WhatsApp/Telegram use."""
    session = await MemoryManager.get_or_create_session(db, channel="widget", customer_identifier=req.session_id)
    await FlowEngine.set_widget_profile(
        db, session,
        name=None if req.skipped else req.name,
        email=None if req.skipped else req.email,
        phone=None if req.skipped else req.phone,
    )
    return {"status": "ok"}


@router.post("/chat/stream")
@limiter.limit("15/minute")
async def widget_chat_stream(request: Request, req: WidgetChatRequest, db: AsyncSession = Depends(get_db)):
    """Streams the LLM response to the website widget using SSE."""

    session = await MemoryManager.get_or_create_session(db, channel="widget", customer_identifier=req.session_id)

    # If session is in profile_collect or quantity_select,
    # intercept free-text input and route to FlowEngine.
    if session.active_flow in ["profile_collect", "quantity_select"]:
        resp = await FlowEngine.handle_action(
            db=db, session=session, action_id=req.message, user_input=req.message,
        )

        async def flow_event_generator():
            yield f"data: {json.dumps({'content': resp.text})}\n\n"
            yield f"data: {json.dumps({'final': resp.model_dump()})}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(flow_event_generator(), media_type="text/event-stream")

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
@limiter.limit("30/minute")
async def widget_action(request: Request, req: WidgetActionRequest, db: AsyncSession = Depends(get_db)) -> BotResponse:
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
@limiter.limit("60/minute")
async def widget_config(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """Minimal launcher metadata for the floating widget (business name, welcome
    message, and whether to show the profile form immediately on open vs. defer
    it to the same chat-based collection WhatsApp/Telegram use at checkout)."""
    stmt = select(ConfigOverride).where(ConfigOverride.key == "business_name")
    res = await db.execute(stmt)
    override = res.scalars().first()
    business_name = override.value if override else settings.APP_NAME

    stmt = select(ConfigOverride).where(ConfigOverride.key == "widget_profile_collection")
    res = await db.execute(stmt)
    mode_override = res.scalars().first()
    profile_collection_mode = mode_override.value if mode_override and mode_override.value in ("upfront", "checkout") else "upfront"

    return {
        "business_name": business_name,
        "welcome_message": f"👋 Hi! How can {business_name} help you today?",
        "profile_collection_mode": profile_collection_mode,
    }
