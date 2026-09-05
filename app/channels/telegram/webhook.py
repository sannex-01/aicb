import json
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import verify_telegram_secret
from app.core.logger import logger
from app.channels.telegram.client import TelegramClient
from app.channels.telegram.render import TelegramRenderer
from app.ai.orchestrator import AIOrchestrator
from app.ai.memory import MemoryManager
from app.flows.engine import FlowEngine
from app.flows.definitions import MAIN_MENU_BUTTONS
from app.schemas.bot_response import BotResponse
from app.telemetry.client import telemetry_client

router = APIRouter(prefix="/webhooks/telegram", tags=["Telegram Webhook"])


async def _deliver(tg_client: TelegramClient, chat_id: int | str, resp: BotResponse) -> None:
    """Sends a BotResponse to Telegram: one swipeable media-group album for
    all product cards (if any) plus a buy-buttons follow-up, then the text
    reply with its own inline keyboard."""
    rendered = TelegramRenderer.render(resp)
    if rendered["photo_items"]:
        album = TelegramRenderer.product_album(rendered["photo_items"])
        if album["media_items"]:
            await tg_client.send_media_group(chat_id=chat_id, items=album["media_items"])
        await tg_client.send_inline_buttons(chat_id=chat_id, text=album["actions_text"], buttons=album["actions_keyboard"])
    if rendered["inline_keyboard"]:
        await tg_client.send_inline_buttons(chat_id=chat_id, text=rendered["text"], buttons=rendered["inline_keyboard"])
    else:
        await tg_client.send_message(chat_id=chat_id, text=rendered["text"])


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

    # 0. Handle Inline Mode Search Queries (bots/inline) — "@botname <query>",
    # either from another chat or via a switch_inline_query_current_chat
    # button in this same chat. No session/flow state involved: this is a
    # stateless search-and-pick, independent of the normal message/callback
    # flow below.
    if "inline_query" in update:
        iq = update["inline_query"]
        iq_id = iq.get("id")
        query_text = (iq.get("query") or "").strip()

        if not query_text:
            await tg_client.answer_inline_query(iq_id, results=[])
        else:
            from app.commerce.catalog_provider import CatalogManager
            from app.commerce.storage.manager import StorageManager
            from app.schemas.bot_response import ProductCard

            products = await CatalogManager.search_products(db, query=query_text, limit=10)
            storage_ok = StorageManager.is_configured()
            cards = [
                ProductCard(
                    id=p.id,
                    title=p.title,
                    description=p.description,
                    price=p.price,
                    currency=p.currency,
                    image_url=p.image_url if storage_ok else None,
                    buy_action_id=f"cart_add_{p.id}",
                )
                for p in products
            ]
            results = TelegramRenderer.inline_query_results(cards)
            await tg_client.answer_inline_query(iq_id, results=results)

        return {"ok": True}

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
        rendered = TelegramRenderer.render(flow_res)

        # Product cards can't be edited in-place onto an existing text message —
        # send a fresh media-group album + its own buy-buttons message, then
        # fall through to the normal edit-or-send text path for the rest.
        if rendered["photo_items"]:
            album = TelegramRenderer.product_album(rendered["photo_items"])
            if album["media_items"]:
                await tg_client.send_media_group(chat_id=chat_id, items=album["media_items"])
            await tg_client.send_inline_buttons(chat_id=chat_id, text=album["actions_text"], buttons=album["actions_keyboard"])

        # Edit the existing message in-place for a clean, app-like experience
        edit_success = False
        if message_id and chat_id:
            try:
                res = await tg_client.edit_inline_buttons(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=rendered["text"],
                    buttons=rendered["inline_keyboard"],
                )
                if res.get("ok"):
                    edit_success = True
            except Exception as e:
                logger.warning(f"In-place message edit failed, will send fresh message: {e}")

        if not edit_success and chat_id:
            if rendered["inline_keyboard"]:
                await tg_client.send_inline_buttons(chat_id=chat_id, text=rendered["text"], buttons=rendered["inline_keyboard"])
            else:
                await tg_client.send_message(chat_id=chat_id, text=rendered["text"])

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
        full_name = " ".join(filter(None, [from_user.get("first_name"), from_user.get("last_name")])) or None
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
        fast_path_triggers = [
            "/start", "start", "menu", "/menu", "help", "/cart", "cart", "checkout",
            "clear cart", "profile", "my profile", "create profile", "update profile", "edit profile",
            "my purchases", "my orders",
        ]
        is_fast_path = (
            text.lower().strip() in fast_path_triggers
            or text.lower().startswith("cart_")
            or text.lower().startswith("flow_")
            or text.lower().startswith("qty_")
        )

        sent_reply_text = ""
        if is_fast_path:
            flow_res = await FlowEngine.handle_action(
                db=db,
                session=session,
                action_id=text,
                user_input=text,
                prefill_name=full_name,
            )
            sent_reply_text = flow_res.text
            await _deliver(tg_client, chat_id, flow_res)
        elif session.active_flow or text.upper().startswith("ORD-"):
            # Active flow state processing (e.g. order tracking or cart input)
            flow_res = await FlowEngine.handle_action(
                db=db,
                session=session,
                action_id=text,
                user_input=text,
                prefill_name=full_name,
            )
            sent_reply_text = flow_res.text
            await _deliver(tg_client, chat_id, flow_res)
        else:
            # Route to AI Orchestrator with graceful button fallback if LLM is unconfigured or errors
            try:
                ai_resp = await AIOrchestrator.process_message(
                    db=db,
                    channel="telegram",
                    customer_identifier=user_id,
                    user_message=text,
                    customer_name=customer_name,
                )
                sent_reply_text = ai_resp.text
                await _deliver(tg_client, chat_id, ai_resp)
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
