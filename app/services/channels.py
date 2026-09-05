import json
import secrets
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.core.config import settings
from app.core.logger import logger


def _mask_secret(val: Optional[str]) -> str:
    if not val:
        return ""
    val = val.strip()
    if len(val) <= 8:
        return "••••••••"
    return f"{val[:4]}••••••••{val[-4:]}"


def generate_webhook_secret() -> str:
    """Generates a cryptographically secure random token for webhook signatures."""
    return f"whsec_{secrets.token_urlsafe(24)}"


def generate_verify_token() -> str:
    """Generates a random verify token for WhatsApp webhook challenge verification."""
    return f"aicb_vt_{secrets.token_hex(16)}"


class ChannelService:
    @staticmethod
    async def get_config(db: AsyncSession) -> Dict[str, Any]:
        """Returns the current messaging channels configuration and webhook URLs."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        
        meta = json.loads(biz.metadata_json or "{}") if biz else {}
        channels_data = meta.get("channels", {})
        
        domain = (settings.AICB_DOMAIN or settings.BOT_DOMAIN or "https://aicb.sannex.ng").rstrip("/")
        
        wa_data = channels_data.get("whatsapp", {})
        wa_verify_token = wa_data.get("verify_token") or settings.META_VERIFY_TOKEN or "aicb_webhook_verification_token_secret"
        wa_app_secret = wa_data.get("app_secret") or settings.META_APP_SECRET or ""

        tg_data = channels_data.get("telegram", {})
        tg_secret = tg_data.get("webhook_secret") or settings.TELEGRAM_WEBHOOK_SECRET
        if not tg_secret:
            tg_secret = generate_webhook_secret()
            # Persist default generated secret if not set
            if biz:
                if "channels" not in meta:
                    meta["channels"] = {}
                meta["channels"]["telegram"] = {"webhook_secret": tg_secret}
                biz.metadata_json = json.dumps(meta)
                await db.commit()

        return {
            "domain": domain,
            "whatsapp": {
                "verify_token": wa_verify_token,
                "app_secret_configured": bool(wa_app_secret),
                "app_secret_masked": _mask_secret(wa_app_secret),
                "webhook_url": f"{domain}/api/v1/webhooks/whatsapp",
            },
            "telegram": {
                "webhook_secret": tg_secret,
                "webhook_secret_configured": bool(tg_secret),
                "webhook_secret_masked": _mask_secret(tg_secret),
                "webhook_url": f"{domain}/api/v1/webhooks/telegram",
            },
        }

    @staticmethod
    async def save_config(db: AsyncSession, config: Dict[str, Any]) -> Dict[str, Any]:
        """Saves messaging channel settings into business metadata."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        existing_channels = meta.get("channels", {})
        existing_wa = existing_channels.get("whatsapp", {})
        existing_tg = existing_channels.get("telegram", {})

        new_wa = config.get("whatsapp", {})
        new_tg = config.get("telegram", {})

        # Merge WhatsApp
        wa_app_secret = new_wa.get("app_secret")
        if wa_app_secret is None or wa_app_secret == "":
            wa_app_secret = existing_wa.get("app_secret", "")

        wa_verify_token = (new_wa.get("verify_token") or existing_wa.get("verify_token") or "aicb_webhook_verification_token_secret").strip()

        merged_wa = {
            "verify_token": wa_verify_token,
            "app_secret": wa_app_secret.strip() if wa_app_secret else "",
        }

        # Merge Telegram
        tg_secret = new_tg.get("webhook_secret")
        if tg_secret is None or tg_secret == "":
            tg_secret = existing_tg.get("webhook_secret") or generate_webhook_secret()

        merged_tg = {
            "webhook_secret": tg_secret.strip() if tg_secret else "",
        }

        meta["channels"] = {
            "whatsapp": merged_wa,
            "telegram": merged_tg,
        }

        biz.metadata_json = json.dumps(meta)
        await db.commit()
        await db.refresh(biz)

        logger.info("Updated global messaging channels settings.")
        return await ChannelService.get_config(db)

    @staticmethod
    async def set_telegram_webhook(bot_token: str, db: AsyncSession) -> Dict[str, Any]:
        """Registers or refreshes the Telegram webhook URL and secret token with Telegram Bot API."""
        if not bot_token or not bot_token.strip():
            return {"ok": False, "description": "No Telegram bot token provided."}

        token = bot_token.strip()
        cfg = await ChannelService.get_config(db)
        webhook_url = cfg["telegram"]["webhook_url"]
        secret_token = cfg["telegram"].get("webhook_secret") or settings.TELEGRAM_WEBHOOK_SECRET or ""

        url = f"https://api.telegram.org/bot{token}/setWebhook"
        payload = {
            "url": webhook_url,
            "allowed_updates": [
                "message",
                "edited_message",
                "callback_query",
                "inline_query",
                "chosen_inline_result",
                "pre_checkout_query",
            ],
        }
        if secret_token:
            payload["secret_token"] = secret_token

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload)
                data = res.json()
                logger.info(f"Telegram setWebhook response: {data}")
                return data
        except Exception as e:
            logger.error(f"Failed to set Telegram webhook: {e}")
            return {"ok": False, "description": str(e)}

