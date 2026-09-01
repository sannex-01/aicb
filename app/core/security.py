import hmac
import hashlib
from typing import Optional
from app.core.config import settings
from app.core.logger import logger


def verify_whatsapp_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    """Verifies X-Hub-Signature-256 header sent by Meta WhatsApp Cloud API."""
    if not settings.META_APP_SECRET:
        return True  # If no secret configured in dev, pass gracefully
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_hash = signature_header[7:]
    generated_hash = hmac.new(
        settings.META_APP_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(generated_hash, expected_hash)


def verify_telegram_secret(secret_header: Optional[str]) -> bool:
    """Verifies X-Telegram-Bot-Api-Secret-Token sent by Telegram webhook."""
    if not settings.TELEGRAM_WEBHOOK_SECRET:
        return True
    if not secret_header:
        return False
    return hmac.compare_digest(settings.TELEGRAM_WEBHOOK_SECRET, secret_header)


def verify_paystack_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    """Verifies x-paystack-signature header using Paystack Secret Key (HMAC-SHA512)."""
    if not settings.PAYSTACK_SECRET_KEY:
        return True
    if not signature_header:
        return False
    computed_signature = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode("utf-8"),
        payload,
        hashlib.sha512
    ).hexdigest()
    return hmac.compare_digest(computed_signature, signature_header)


def verify_flutterwave_hash(hash_header: Optional[str]) -> bool:
    """Verifies verif-hash header sent by Flutterwave."""
    if not settings.FLUTTERWAVE_SECRET_HASH:
        return True
    if not hash_header:
        return False
    return hmac.compare_digest(settings.FLUTTERWAVE_SECRET_HASH, hash_header)


def verify_stripe_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    """Verifies Stripe signature header (t=timestamp,v1=signature)."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    try:
        elements = dict(item.split("=", 1) for item in signature_header.split(","))
        timestamp = elements.get("t")
        sig = elements.get("v1")
        if not timestamp or not sig:
            return False
        signed_payload = f"{timestamp}.".encode("utf-8") + payload
        expected_sig = hmac.new(
            settings.STRIPE_WEBHOOK_SECRET.encode("utf-8"),
            signed_payload,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected_sig, sig)
    except Exception as e:
        logger.error(f"Error validating stripe signature: {e}")
        return False
