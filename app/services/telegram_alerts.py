import json
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.models.agent import Agent
from app.models.order import Order
from app.models.session import ConversationSession
from app.channels.telegram.client import TelegramClient
from app.core.logger import logger


class TelegramAlertService:
    """Telegram order alerts sent via whichever AGENT actually sold the
    order (its own telegram_bot_token — the same bot already used for
    customer conversations) rather than a separate, dedicated alerts bot a
    business would otherwise have to create and maintain. All a business
    configures here is WHERE alerts go: a group chat_id (add any of your
    Telegram-connected agents' bots to that group). Config lives on
    BusinessProfile.metadata_json["telegram_alerts"] = {"chat_id": ...}.

    Telegram's sendMessage API treats a group chat_id (a negative number,
    e.g. -1001234567890) exactly like a personal one — a lone chat_id
    still works fine for a business that just wants alerts to themselves."""

    @staticmethod
    async def get_config(db: AsyncSession) -> Dict[str, Any]:
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        chat_id = ""
        if biz:
            meta = json.loads(biz.metadata_json or "{}")
            chat_id = meta.get("telegram_alerts", {}).get("chat_id", "")

        has_bot = await TelegramAlertService._any_agent_has_bot(db)

        return {
            "configured": bool(chat_id) and has_bot,
            "config": {
                "chat_id": chat_id,
                "has_telegram_bot": has_bot,
            },
        }

    @staticmethod
    async def _any_agent_has_bot(db: AsyncSession) -> bool:
        stmt = select(Agent).where(Agent.telegram_bot_token.isnot(None), Agent.telegram_bot_token != "")
        res = await db.execute(stmt)
        return res.scalars().first() is not None

    @staticmethod
    async def save_config(db: AsyncSession, config: Dict[str, Any]) -> Dict[str, Any]:
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        chat_id = (config.get("chat_id") or "").strip()

        if chat_id:
            has_bot = await TelegramAlertService._any_agent_has_bot(db)
            if not has_bot:
                raise ValueError("No agent has a Telegram bot connected yet — set one up on an agent in AI Agents Studio first, then come back and save this group chat ID.")

        meta["telegram_alerts"] = {"chat_id": chat_id}
        biz.metadata_json = json.dumps(meta)
        await db.commit()

        return await TelegramAlertService.get_config(db)

    @staticmethod
    async def _resolve_sending_bot_token(db: AsyncSession, order: Optional[Order]) -> Optional[str]:
        """Prefers the bot belonging to whichever agent actually sold this
        order (via the order's own channel+customer_identifier -> the
        ConversationSession that handled it -> its agent_id) — falls back
        to any agent with a Telegram bot configured if that agent has none
        (e.g. the sale came through WhatsApp/widget) or can't be resolved."""
        if order is not None:
            try:
                session_key = f"{order.channel}:{order.customer_identifier}"
                sess_res = await db.execute(select(ConversationSession).where(ConversationSession.session_key == session_key))
                session = sess_res.scalar_one_or_none()
                if session and session.agent_id:
                    agent_res = await db.execute(select(Agent).where(Agent.id == session.agent_id))
                    agent = agent_res.scalar_one_or_none()
                    if agent and agent.telegram_bot_token:
                        return agent.telegram_bot_token
            except Exception as e:
                logger.warning(f"Could not resolve selling agent's Telegram bot for order alert: {e}")

        fallback_res = await db.execute(select(Agent).where(Agent.telegram_bot_token.isnot(None), Agent.telegram_bot_token != "").limit(1))
        fallback_agent = fallback_res.scalar_one_or_none()
        return fallback_agent.telegram_bot_token if fallback_agent else None

    @staticmethod
    async def send_alert(db: AsyncSession, message: str, order: Optional[Order] = None) -> bool:
        """Sends an alert message via the resolved bot. Raises on failure/
        misconfiguration — callers needing best-effort behavior should
        catch this themselves. `order`, when given, is used to prefer the
        specific agent that sold it (see _resolve_sending_bot_token)."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            raise ValueError("Business profile not found.")

        meta = json.loads(biz.metadata_json or "{}")
        chat_id = meta.get("telegram_alerts", {}).get("chat_id")
        if not chat_id:
            raise ValueError("Telegram alerts are not configured. Please set a group chat ID in Integrations → Order Alerts.")

        bot_token = await TelegramAlertService._resolve_sending_bot_token(db, order)
        if not bot_token:
            raise ValueError("No agent has a Telegram bot connected — set one up on an agent in AI Agents Studio first.")

        client = TelegramClient(token=bot_token)
        result = await client.send_message(chat_id=chat_id, text=message)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram alert failed: {result.get('description', 'unknown error')}")
        return True
