import json
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.core.logger import logger


class SMSService:
    """BYO-key SMS delivery, mirroring EmailService's shape exactly —
    config lives on BusinessProfile.metadata_json["sms"], masked previews
    are safe to return to the dashboard, and the actual key is only ever
    read server-side when sending. Supports Africa's Talking and Termii,
    the two providers with genuinely usable, well-documented public APIs
    for Nigerian/African SMS delivery."""

    @staticmethod
    async def get_config(db: AsyncSession) -> Dict[str, Any]:
        """Returns the current SMS delivery configuration with API keys masked."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            return {"provider": None, "configured": False, "config": {}}

        meta = json.loads(biz.metadata_json or "{}")
        sms_data = meta.get("sms", {})
        provider = sms_data.get("provider")
        raw_config = sms_data.get("config", {})

        safe_config = {}
        if provider == "africastalking":
            api_key = raw_config.get("api_key", "")
            masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("***" if api_key else "")
            safe_config = {
                "api_key_masked": masked_key,
                "api_key_configured": bool(api_key),
                "username": raw_config.get("username", ""),
                "sender_id": raw_config.get("sender_id", ""),
            }
        elif provider == "termii":
            api_key = raw_config.get("api_key", "")
            masked_key = f"{api_key[:6]}...{api_key[-4:]}" if len(api_key) > 10 else ("***" if api_key else "")
            safe_config = {
                "api_key_masked": masked_key,
                "api_key_configured": bool(api_key),
                "sender_id": raw_config.get("sender_id", ""),
            }

        configured = bool(provider == "africastalking" and raw_config.get("api_key") and raw_config.get("username")) or \
            bool(provider == "termii" and raw_config.get("api_key"))

        return {
            "provider": provider,
            "configured": configured,
            "config": safe_config,
        }

    @staticmethod
    async def save_config(db: AsyncSession, provider: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
        """Saves SMS provider settings into business metadata."""
        clean_provider = provider.lower().strip() if provider and provider != "none" else None

        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        existing_sms = meta.get("sms", {})
        existing_config = existing_sms.get("config", {})
        existing_provider = existing_sms.get("provider")

        def _resolve_key(new_key: str) -> str:
            new_key = (new_key or "").strip()
            if (not new_key or new_key.startswith("***") or "..." in new_key) and existing_provider == clean_provider:
                return existing_config.get("api_key", "").strip()
            return new_key

        if clean_provider == "africastalking":
            final_api_key = _resolve_key(config.get("api_key"))
            if not final_api_key:
                raise ValueError("API Key is required to configure Africa's Talking SMS delivery.")
            username = (config.get("username") or "").strip()
            if not username:
                raise ValueError("Username is required for Africa's Talking (use 'sandbox' for testing).")
            sender_id = (config.get("sender_id") or "").strip()

            meta["sms"] = {
                "provider": "africastalking",
                "config": {"api_key": final_api_key, "username": username, "sender_id": sender_id},
            }
        elif clean_provider == "termii":
            final_api_key = _resolve_key(config.get("api_key"))
            if not final_api_key:
                raise ValueError("API Key is required to configure Termii SMS delivery.")
            sender_id = (config.get("sender_id") or "").strip()
            if not sender_id:
                raise ValueError("Sender ID is required for Termii (must be an approved sender ID on your account).")

            meta["sms"] = {
                "provider": "termii",
                "config": {"api_key": final_api_key, "sender_id": sender_id},
            }
        elif not clean_provider:
            meta["sms"] = {"provider": None, "config": {}}
        else:
            raise ValueError(f"Unsupported SMS provider: {clean_provider}. Choose 'africastalking' or 'termii'.")

        biz.metadata_json = json.dumps(meta)
        await db.commit()

        return await SMSService.get_config(db)

    @staticmethod
    async def send_sms(db: AsyncSession, to_phone: str, message: str) -> bool:
        """Sends an SMS via the configured provider. Raises on failure —
        callers that need "best effort, don't crash the caller" behavior
        (like the multi-channel order-alert dispatcher) should catch this
        themselves, same as they already do around SlackDispatcher/other
        per-channel sends."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            raise ValueError("Business profile not found.")

        meta = json.loads(biz.metadata_json or "{}")
        sms_data = meta.get("sms", {})
        provider = sms_data.get("provider")
        config = sms_data.get("config", {})

        if not provider or not config.get("api_key"):
            raise ValueError("SMS delivery is not configured. Please configure Africa's Talking or Termii in Settings.")

        async with httpx.AsyncClient(timeout=15.0) as client:
            if provider == "africastalking":
                resp = await client.post(
                    "https://api.africastalking.com/version1/messaging/bulk",
                    headers={
                        "apiKey": config["api_key"],
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Accept": "application/json",
                    },
                    data={
                        "username": config.get("username", "sandbox"),
                        "phoneNumbers": to_phone,
                        "message": message,
                        **({"senderId": config["sender_id"]} if config.get("sender_id") else {}),
                    },
                )
                if resp.status_code not in [200, 201]:
                    raise RuntimeError(f"Africa's Talking error ({resp.status_code}): {resp.text}")
                data = resp.json()
                recipients = data.get("SMSMessageData", {}).get("Recipients", [])
                if recipients and recipients[0].get("status") != "Success":
                    raise RuntimeError(f"Africa's Talking rejected the message: {recipients[0].get('status')}")
                return True

            elif provider == "termii":
                resp = await client.post(
                    "https://api.ng.termii.com/api/sms/send",
                    headers={"Content-Type": "application/json"},
                    json={
                        "api_key": config["api_key"],
                        "to": to_phone,
                        "from": config.get("sender_id", ""),
                        "sms": message,
                        "type": "plain",
                        "channel": "dnd",
                    },
                )
                if resp.status_code not in [200, 201]:
                    err_msg = resp.text
                    try:
                        err_msg = resp.json().get("message", resp.text)
                    except Exception:
                        pass
                    raise RuntimeError(f"Termii error ({resp.status_code}): {err_msg}")
                return True

            else:
                raise ValueError(f"Unsupported SMS provider: {provider}")
