import json
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import logger

FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/v3"


class FlutterwaveClient:
    """Flutterwave Payments Integration."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or settings.FLUTTERWAVE_SECRET_KEY

    def _headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise ValueError("FLUTTERWAVE_SECRET_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/json",
        }

    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        email: str,
        reference: str,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        redirect_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Creates a standard payment link on Flutterwave."""
        url = f"{FLUTTERWAVE_BASE_URL}/payments"

        payload = {
            "tx_ref": reference,
            "amount": amount,
            "currency": currency.upper(),
            "redirect_url": redirect_url or settings.PAYSTACK_CALLBACK_URL,
            "customer": {
                "email": email,
                "phonenumber": customer_phone or "",
                "name": customer_name or "Customer",
            },
            "meta": metadata or {},
            "customizations": {
                "title": settings.APP_NAME,
                "description": f"Payment for Order {reference}",
            },
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=self._headers())
            data = res.json()
            if res.status_code == 200 and data.get("status") == "success":
                return {
                    "checkout_url": data["data"]["link"],
                    "reference": reference,
                }
            else:
                logger.error(f"Flutterwave init failed: {res.status_code} - {res.text}")
                raise RuntimeError(data.get("message", "Flutterwave payment initialization failed"))

    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Verifies transaction on Flutterwave via transaction ID."""
        url = f"{FLUTTERWAVE_BASE_URL}/transactions/{transaction_id}/verify"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=self._headers())
            data = res.json()
            if res.status_code == 200 and data.get("status") == "success":
                tx = data["data"]
                return {
                    "status": "success" if tx.get("status") == "successful" else tx.get("status"),
                    "amount": tx.get("amount"),
                    "currency": tx.get("currency"),
                    "reference": tx.get("tx_ref"),
                    "raw": tx,
                }
            else:
                raise RuntimeError(data.get("message", "Flutterwave verification failed"))
