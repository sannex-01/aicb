import json
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.commerce.customer_profile import is_valid_email, is_valid_phone


class AlertRecipientsService:
    """Who order alerts actually get sent to, for the two channels that
    don't already carry a recipient inside their own config: Email
    (Resend/Brevo config only has sender identity — from_email/from_name,
    not who receives the alert) and SMS (Africa's Talking/Termii config is
    pure provider credentials). Telegram doesn't need this — its chat_id
    IS the recipient, already stored on TelegramAlertService's own config.

    Config lives on BusinessProfile.metadata_json["order_alert_recipients"]
    = {"emails": [...], "phones": [...]}."""

    @staticmethod
    async def get_recipients(db: AsyncSession) -> Dict[str, List[str]]:
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            return {"emails": [], "phones": []}
        meta = json.loads(biz.metadata_json or "{}")
        data = meta.get("order_alert_recipients", {})
        return {"emails": data.get("emails", []), "phones": data.get("phones", [])}

    @staticmethod
    async def save_recipients(db: AsyncSession, emails: List[str], phones: List[str]) -> Dict[str, List[str]]:
        clean_emails = [e.strip() for e in emails if e and e.strip()]
        clean_phones = [p.strip() for p in phones if p and p.strip()]

        bad_emails = [e for e in clean_emails if not is_valid_email(e)]
        if bad_emails:
            raise ValueError(f"Invalid email address(es): {', '.join(bad_emails)}")
        bad_phones = [p for p in clean_phones if not is_valid_phone(p)]
        if bad_phones:
            raise ValueError(f"Invalid phone number(s): {', '.join(bad_phones)}")

        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        meta["order_alert_recipients"] = {"emails": clean_emails, "phones": clean_phones}
        biz.metadata_json = json.dumps(meta)
        await db.commit()

        return await AlertRecipientsService.get_recipients(db)
