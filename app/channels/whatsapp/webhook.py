import json
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Request, Response, Depends, Header, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_whatsapp_signature
from app.core.logger import logger
from app.channels.whatsapp.client import WhatsAppClient
from app.ai.orchestrator import AIOrchestrator
from app.ai.memory import MemoryManager
from app.flows.engine import FlowEngine
from app.telemetry.client import telemetry_client

router = APIRouter(prefix="/webhooks/whatsapp", tags=["WhatsApp Webhook"])


@router.get("")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """WhatsApp Cloud API Webhook Verification Challenge."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        logger.info("WhatsApp webhook verified successfully.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning("WhatsApp webhook verification failed.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("")
async def handle_whatsapp_message(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Receives and processes incoming WhatsApp messages and interactive actions."""
    raw_body = await request.body()
    if not verify_whatsapp_signature(raw_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid WhatsApp signature")

    try:
        data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ok"}

    wa_client = WhatsAppClient()

    # Iterate through WhatsApp payload structure
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                wa_id = msg.get("from")
                msg_type = msg.get("type")
                user_text = ""
                action_id = None

                # Extract customer name if present
                contacts = value.get("contacts", [])
                customer_name = contacts[0].get("profile", {}).get("name") if contacts else None

                # 1. Text Message
                if msg_type == "text":
                    user_text = msg.get("text", {}).get("body", "").strip()

                # 2. Interactive Quick-Reply Button Click
                elif msg_type == "interactive":
                    interactive = msg.get("interactive", {})
                    interactive_type = interactive.get("type")
                    if interactive_type == "button_reply":
                        action_id = interactive.get("button_reply", {}).get("id")
                        user_text = interactive.get("button_reply", {}).get("title", "")
                    elif interactive_type == "list_reply":
                        action_id = interactive.get("list_reply", {}).get("id")
                        user_text = interactive.get("list_reply", {}).get("title", "")

                if not user_text and not action_id:
                    continue

                logger.info(f"Incoming WhatsApp message from {wa_id}: '{user_text}' (action: {action_id})")

                # Track telemetry event
                telemetry_client.track(
                    channel="whatsapp",
                    customer_id=wa_id,
                    event="message_received",
                    metadata={"msg_type": msg_type, "text": user_text[:100]},
                )

                session = await MemoryManager.get_or_create_session(db, channel="whatsapp", customer_identifier=wa_id)

                # Determine Routing: Fast-Path System Handlers (0 LLM Tokens) vs AI Orchestration
                fast_path_triggers = ["menu", "start", "/start", "help", "cart", "/cart", "checkout", "clear cart"]
                is_fast_path = (
                    action_id
                    or user_text.lower().strip() in fast_path_triggers
                    or user_text.lower().startswith("cart_")
                    or user_text.lower().startswith("flow_")
                )

                if is_fast_path:
                    flow_res = await FlowEngine.handle_action(
                        db=db,
                        session=session,
                        action_id=action_id or user_text,
                        user_input=user_text,
                    )
                    if flow_res.get("type") == "buttons":
                        await wa_client.send_button_message(
                            to=wa_id,
                            body=flow_res["text"],
                            buttons=flow_res["buttons"],
                        )
                    else:
                        await wa_client.send_text_message(to=wa_id, body=flow_res["text"])
                else:
                    # Route to AI Orchestrator
                    ai_reply = await AIOrchestrator.process_message(
                        db=db,
                        channel="whatsapp",
                        customer_identifier=wa_id,
                        user_message=user_text,
                        customer_name=customer_name,
                    )
                    
                    # WhatsApp doesn't support free-form URL buttons, so we convert markdown links to text
                    import re
                    def format_wa_links(match):
                        return f"*{match.group(1)}*: {match.group(2)}"
                    
                    formatted_reply = re.sub(r"\[(.*?)\]\((.*?)\)", format_wa_links, ai_reply)
                    
                    await wa_client.send_text_message(to=wa_id, body=formatted_reply)

                # Track outgoing message telemetry
                telemetry_client.track(
                    channel="whatsapp",
                    customer_id=wa_id,
                    event="message_sent",
                )

    return {"status": "ok"}
