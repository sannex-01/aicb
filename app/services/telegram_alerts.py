import json
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.channels.telegram.client import TelegramClient


class TelegramAlertService:
    """BYO-key Telegram order alerts, mirroring EmailService/SMSService's
    shape. Deliberately a SEPARATE bot from whatever the business uses for
    customer-facing conversations — a business owner creates a small
    second bot via @BotFather purely for order alerts, pastes its token
    plus their own numeric Telegram user id (the chat_id to send alerts
    to) here. Config lives on BusinessProfile.metadata_json["telegram_alerts"]."""

    @staticmethod
    async def get_config(db: AsyncSession) -> Dict[str, Any]:
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            return {"configured": False, "config": {}}

        meta = json.loads(biz.metadata_json or "{}")
        data = meta.get("telegram_alerts", {})
        bot_token = data.get("bot_token", "")
        chat_id = data.get("chat_id", "")

        masked_token = f"{bot_token[:8]}...{bot_token[-4:]}" if len(bot_token) > 14 else ("***" if bot_token else "")

        return {
            "configured": bool(bot_token and chat_id),
            "config": {
                "bot_token_masked": masked_token,
                "bot_token_configured": bool(bot_token),
                "chat_id": chat_id,
            },
        }

    @staticmethod
    async def save_config(db: AsyncSession, config: Dict[str, Any]) -> Dict[str, Any]:
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        existing = meta.get("telegram_alerts", {})

        # Reuse the existing saved token only when the caller sent a masked
        # placeholder (echoing back what get_config returned) or omitted
        # the field (None) — NOT when they explicitly sent "" to clear it.
        # An empty string is a deliberate clear; conflating it with
        # "unspecified" made it impossible to ever actually disable this
        # channel once a real token had been saved.
        raw_token = config.get("bot_token")
        if raw_token is None:
            final_token = existing.get("bot_token", "").strip()
        else:
            stripped = raw_token.strip()
            if stripped.startswith("***") or "..." in stripped:
                final_token = existing.get("bot_token", "").strip()
            else:
                final_token = stripped  # "" here means "clear it", intentionally

        chat_id = (config.get("chat_id") or "").strip()

        if not final_token and not chat_id:
            # Both cleared — treat as "disable this channel"
            meta["telegram_alerts"] = {"bot_token": "", "chat_id": ""}
        else:
            if not final_token:
                raise ValueError("Bot Token is required. Create a bot via @BotFather in Telegram and paste its token here.")
            if not chat_id:
                raise ValueError("Chat ID is required — send /start to your alerts bot, then use @userinfobot to find your numeric Telegram user ID.")
            meta["telegram_alerts"] = {"bot_token": final_token, "chat_id": chat_id}

        biz.metadata_json = json.dumps(meta)
        await db.commit()

        return await TelegramAlertService.get_config(db)

    @staticmethod
    async def send_alert(db: AsyncSession, message: str) -> bool:
        """Sends an alert message via the configured alerts bot. Raises on
        failure/misconfiguration — callers needing best-effort behavior
        should catch this themselves."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            raise ValueError("Business profile not found.")

        meta = json.loads(biz.metadata_json or "{}")
        data = meta.get("telegram_alerts", {})
        bot_token = data.get("bot_token")
        chat_id = data.get("chat_id")

        if not bot_token or not chat_id:
            raise ValueError("Telegram alerts are not configured. Please set up your alerts bot in Settings.")

        client = TelegramClient(token=bot_token)
        result = await client.send_message(chat_id=chat_id, text=message)
        if not result.get("ok"):
            raise RuntimeError(f"Telegram alert failed: {result.get('description', 'unknown error')}")
        return True
