import json
from typing import Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import BusinessProfile
from app.core.config import settings
from app.core.logger import logger


def _mask_key(key: Optional[str]) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "***"
    return f"{key[:6]}...{key[-4:]}"


CURRENCY_METADATA = {
    "NGN": {"code": "NGN", "symbol": "₦", "name": "Nigerian Naira"},
    "USD": {"code": "USD", "symbol": "$", "name": "US Dollar"},
    "GHS": {"code": "GHS", "symbol": "GH₵", "name": "Ghanaian Cedi"},
    "KES": {"code": "KES", "symbol": "KSh", "name": "Kenyan Shilling"},
    "ZAR": {"code": "ZAR", "symbol": "R", "name": "South African Rand"},
    "EUR": {"code": "EUR", "symbol": "€", "name": "Euro"},
    "GBP": {"code": "GBP", "symbol": "£", "name": "British Pound"},
    "EGP": {"code": "EGP", "symbol": "E£", "name": "Egyptian Pound"},
    "CAD": {"code": "CAD", "symbol": "CA$", "name": "Canadian Dollar"},
}


class PaymentService:
    @staticmethod
    async def get_currencies(db: AsyncSession) -> list:
        """Fetches the merchant's available currencies from Paystack with structured metadata."""
        from app.commerce.payments.paystack import PaystackClient

        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()

        meta = json.loads(biz.metadata_json or "{}") if biz else {}
        pay_data = meta.get("payments", {})
        raw_config = pay_data.get("config", {})

        sk = raw_config.get("secret_key") or settings.PAYSTACK_SECRET_KEY
        client = PaystackClient(secret_key=sk)
        raw_codes = await client.get_available_currencies()

        formatted = []
        for code in raw_codes:
            code_upper = code.upper().strip()
            item = CURRENCY_METADATA.get(code_upper, {
                "code": code_upper,
                "symbol": code_upper,
                "name": code_upper,
            })
            formatted.append({
                "code": item["code"],
                "symbol": item["symbol"],
                "name": item["name"],
                "label": f"{item['code']} ({item['symbol']}) - {item['name']}",
            })
        return formatted

    @staticmethod
    async def get_config(db: AsyncSession) -> Dict[str, Any]:
        """Returns the single active payment gateway configuration with secrets masked and available currencies."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()

        meta = json.loads(biz.metadata_json or "{}") if biz else {}
        pay_data = meta.get("payments", {})
        provider = pay_data.get("provider")
        if not provider and "default_gateway" in pay_data and "gateways" in pay_data:
            provider = pay_data.get("default_gateway")
        if provider == "none":
            provider = None

        raw_config = pay_data.get("config", {})

        # Fallback migration support from legacy multi-gateway dictionary
        if not raw_config and "gateways" in pay_data and provider:
            raw_config = pay_data["gateways"].get(provider, {})

        safe_config = {}
        is_configured = False

        if provider == "paystack":
            sk = raw_config.get("secret_key") or settings.PAYSTACK_SECRET_KEY
            pk = raw_config.get("public_key") or getattr(settings, "PAYSTACK_PUBLIC_KEY", "")
            is_configured = bool(sk)
            safe_config = {
                "secret_key_masked": _mask_key(sk),
                "secret_key_configured": bool(sk),
                "public_key": pk or "",
            }
        else:
            provider = None

        currencies = await PaymentService.get_currencies(db)

        return {
            "provider": provider,
            "configured": is_configured,
            "config": safe_config,
            "available_currencies": currencies,
        }

    @staticmethod
    async def save_config(db: AsyncSession, provider: Optional[str], config: Dict[str, Any]) -> Dict[str, Any]:
        """Saves the Paystack payment provider configuration safely with validation."""
        res = await db.execute(select(BusinessProfile).limit(1))
        biz = res.scalar_one_or_none()
        if not biz:
            biz = BusinessProfile()
            db.add(biz)

        meta = json.loads(biz.metadata_json or "{}")
        existing_payments = meta.get("payments", {})
        existing_config = existing_payments.get("config", {})
        existing_provider = existing_payments.get("provider")

        clean_provider = provider.lower().strip() if provider and provider != "none" else None

        merged_config = dict(existing_config) if existing_provider == clean_provider else {}
        incoming_config = dict(config or {})

        if clean_provider == "paystack":
            sk = (incoming_config.get("secret_key") or "").strip()
            if (not sk or sk.startswith("***") or "..." in sk) and existing_provider == "paystack":
                sk = (existing_config.get("secret_key") or "").strip()
            if not sk:
                raise ValueError("Secret Key is required to configure Paystack.")

            merged_config["secret_key"] = sk
            if "public_key" in incoming_config:
                merged_config["public_key"] = (incoming_config.get("public_key") or "").strip()

        elif clean_provider is not None:
            raise ValueError(f"Unsupported payment gateway: '{clean_provider}'. Currently, only 'paystack' is supported.")

        meta["payments"] = {
            "provider": clean_provider,
            "default_gateway": clean_provider,
            "config": merged_config if clean_provider else {},
        }
        biz.metadata_json = json.dumps(meta)
        await db.commit()

        return await PaymentService.get_config(db)
