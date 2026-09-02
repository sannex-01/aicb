import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_telegram_secret
from app.core.logger import logger
from app.channels.telegram.client import TelegramClient
from app.ai.orchestrator import AIOrchestrator
from app.ai.memory import MemoryManager
from app.flows.engine import FlowEngine
from app.telemetry.client import telemetry_client

router = APIRouter(prefix="/webhooks/telegram", tags=["Telegram Webhook"])


@router.post("")
async def handle_telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    """Processes incoming updates from Telegram Bot API."""
    if not verify_telegram_secret(x_telegram_bot_api_secret_token):
        raise HTTPException(status_code=401, detail="Invalid Telegram secret token")

    raw_body = await request.body()
    try:
        update = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"ok": True}

    tg_client = TelegramClient()

    # 1. Handle Inline Button Clicks (callback_query)
    if "callback_query" in update:
        cb = update["callback_query"]
        cb_id = cb.get("id")
        action_data = cb.get("data", "")
        from_user = cb.get("from", {})
        user_id = str(from_user.get("id"))
        message_obj = cb.get("message", {})
        chat_id = message_obj.get("chat", {}).get("id")
        message_id = message_obj.get("message_id")

        await tg_client.answer_callback_query(cb_id)

        session = await MemoryManager.get_or_create_session(db, channel="telegram", customer_identifier=user_id)
        flow_res = await FlowEngine.handle_action(
            db=db,
            session=session,
            action_id=action_data,
            user_input=action_data,
        )

        inline_kb = None
        if flow_res.get("type") == "buttons" and flow_res.get("buttons"):
            inline_kb = [
                [{"text": b["title"], "callback_data": b["id"]}]
                for b in flow_res["buttons"]
            ]

        # Edit the existing message in-place for a clean, app-like experience
        edit_success = False
        if message_id and chat_id:
            try:
                res = await tg_client.edit_inline_buttons(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=flow_res["text"],
                    buttons=inline_kb,
                )
                if res.get("ok"):
                    edit_success = True
            except Exception as e:
                logger.warning(f"In-place message edit failed, will send fresh message: {e}")

        if not edit_success and chat_id:
            if inline_kb:
                await tg_client.send_inline_buttons(chat_id=chat_id, text=flow_res["text"], buttons=inline_kb)
            else:
                await tg_client.send_message(chat_id=chat_id, text=flow_res["text"])

        # Track interactive button action telemetry
        telemetry_client.track(
            channel="telegram",
            customer_id=user_id,
            event="button_click",
            metadata={"action": action_data[:100]},
        )

        return {"ok": True}

    # 2. Handle Inbound Text Messages
    if "message" in update:
        msg = update["message"]
        chat_id = msg.get("chat", {}).get("id")
        from_user = msg.get("from", {})
        user_id = str(from_user.get("id"))
        customer_name = from_user.get("first_name", "Telegram User")
        text = msg.get("text", "").strip()

        # Handle native Telegram successful payment notification
        if "successful_payment" in msg:
            sp = msg["successful_payment"]
            logger.info(f"Telegram in-app payment successful for user {user_id}: {sp}")
            telemetry_client.track(
                channel="telegram",
                customer_id=user_id,
                event="payment_success",
                amount=sp.get("total_amount", 0) / 100.0,
                status="success",
            )
            await tg_client.send_message(
                chat_id=chat_id,
                text="🎉 *Payment Confirmed!* Thank you for your purchase. We are processing your order right away.",
            )
            return {"ok": True}

        if not text:
            return {"ok": True}

        logger.info(f"Incoming Telegram message from {user_id} (@{from_user.get('username')}): '{text}'")

        telemetry_client.track(
            channel="telegram",
            customer_id=user_id,
            event="message_received",
            metadata={"text": text[:100]},
        )

        session = await MemoryManager.get_or_create_session(db, channel="telegram", customer_identifier=user_id)

        # Handle Fast-Path System Handlers (0 LLM Tokens)
        fast_path_triggers = ["/start", "start", "menu", "/menu", "help", "/cart", "cart", "checkout", "clear cart"]
        is_fast_path = (
            text.lower().strip() in fast_path_triggers
            or text.lower().startswith("cart_")
            or text.lower().startswith("flow_")
        )

        sent_reply_text = ""
        if is_fast_path:
            flow_res = await FlowEngine.handle_action(
                db=db,
                session=session,
                action_id=text,
                user_input=text,
            )
            sent_reply_text = flow_res.get("text", "")
            inline_kb = [
                [{"text": b["title"], "callback_data": b["id"]}]
                for b in flow_res.get("buttons", [])
            ]
            await tg_client.send_inline_buttons(chat_id=chat_id, text=flow_res["text"], buttons=inline_kb)
        elif session.active_flow or text.upper().startswith("ORD-"):
            # Active flow state processing (e.g. order tracking or cart input)
            flow_res = await FlowEngine.handle_action(
                db=db,
                session=session,
                action_id=text,
                user_input=text,
            )
            sent_reply_text = flow_res.get("text", "")
            inline_kb = [
                [{"text": b["title"], "callback_data": b["id"]}]
                for b in flow_res.get("buttons", [])
            ]
            if inline_kb:
                await tg_client.send_inline_buttons(chat_id=chat_id, text=flow_res["text"], buttons=inline_kb)
            else:
                await tg_client.send_message(chat_id=chat_id, text=flow_res["text"])
        else:
            # Route to AI Orchestrator with graceful button fallback if LLM is unconfigured or errors
            try:
                ai_reply = await AIOrchestrator.process_message(
                    db=db,
                    channel="telegram",
                    customer_identifier=user_id,
                    user_message=text,
                    customer_name=customer_name,
                )
                
                import re
                inline_kb = []
                
                def extract_tg_links(match):
                    title = match.group(1)
                    url = match.group(2)
                    inline_kb.append([{"text": title, "url": url}])
                    return ""
                    
                formatted_reply = re.sub(r"\[(.*?)\]\((.*?)\)", extract_tg_links, ai_reply).strip()
                if not formatted_reply and inline_kb:
                    formatted_reply = "Please see the link below:"
                sent_reply_text = formatted_reply
                    
                if inline_kb:
                    await tg_client.send_inline_buttons(chat_id=chat_id, text=formatted_reply, buttons=inline_kb)
                else:
                    await tg_client.send_message(chat_id=chat_id, text=formatted_reply)
            except Exception as e:
                logger.warning(f"AI Orchestrator unavailable ({e}). Falling back to interactive menu buttons.")
                fallback_kb = [
                    [{"text": b["title"], "callback_data": b["id"]}]
                    for b in MAIN_MENU_BUTTONS
                ]
                sent_reply_text = "👋 I received your message! Please select from our interactive menu below to browse products, check your cart, or track an order:"
                await tg_client.send_inline_buttons(
                    chat_id=chat_id,
                    text=sent_reply_text,
                    buttons=fallback_kb,
                )

        telemetry_client.track(
            channel="telegram",
            customer_id=user_id,
            event="message_sent",
        )

        # Sync conversation transcript so Conversations CRM in AgentOS updates in real time
        telemetry_client.sync_conversation(
            channel="telegram",
            customer_id=user_id,
            messages=[
                {"role": "user", "content": text},
                {"role": "assistant", "content": sent_reply_text or "Interactive menu sent"},
            ],
        )

    # 3. Handle Pre-Checkout Query for Telegram Payments
    if "pre_checkout_query" in update:
        pcq = update["pre_checkout_query"]
        pcq_id = pcq.get("id")
        await tg_client.answer_pre_checkout_query(pcq_id, ok=True)
        return {"ok": True}

    return {"ok": True}
