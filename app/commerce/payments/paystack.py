import json
from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings
from app.core.security import verify_paystack_signature
from app.core.logger import logger

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackClient:
    """Paystack Payments & Products API integration."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or settings.PAYSTACK_SECRET_KEY

    def _headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise ValueError("PAYSTACK_SECRET_KEY is not configured.")
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
        callback_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Initializes a transaction on Paystack (amount converted to kobo/cents)."""
        amount_kobo = int(round(amount * 100))
        url = f"{PAYSTACK_BASE_URL}/transaction/initialize"

        payload = {
            "amount": amount_kobo,
            "currency": currency.upper(),
            "email": email,
            "reference": reference,
            "callback_url": callback_url or settings.PAYSTACK_CALLBACK_URL,
            "metadata": metadata or {},
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=self._headers())
            data = res.json()
            if res.status_code == 200 and data.get("status"):
                return {
                    "checkout_url": data["data"]["authorization_url"],
                    "access_code": data["data"]["access_code"],
                    "reference": data["data"]["reference"],
                }
            else:
                logger.error(f"Paystack init failed: {res.status_code} - {res.text}")
                raise RuntimeError(data.get("message", "Paystack payment initialization failed"))

    async def verify_payment(self, reference: str) -> Dict[str, Any]:
        """Verifies a transaction status on Paystack."""
        url = f"{PAYSTACK_BASE_URL}/transaction/verify/{reference}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=self._headers())
            data = res.json()
            if res.status_code == 200 and data.get("status"):
                tx_data = data["data"]
                return {
                    "status": tx_data.get("status"), # success, failed, abandoned
                    "amount": tx_data.get("amount", 0) / 100.0,
                    "currency": tx_data.get("currency"),
                    "reference": tx_data.get("reference"),
                    "customer": tx_data.get("customer", {}),
                    "raw": tx_data,
                }
            else:
                raise RuntimeError(data.get("message", "Paystack verification failed"))

    async def fetch_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches product catalog from Paystack Products API."""
        url = f"{PAYSTACK_BASE_URL}/product?perPage={limit}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=self._headers())
            data = res.json()
            if res.status_code == 200 and data.get("status"):
                products = []
                for p in data.get("data", []):
                    # Paystack product structure
                    price = (p.get("price") or 0) / 100.0
                    products.append({
                        "external_id": str(p.get("id")),
                        "title": p.get("name"),
                        "description": p.get("description", ""),
                        "price": price,
                        "currency": p.get("currency", "NGN"),
                        "in_stock": not p.get("is_shippable", False) or (p.get("quantity", 1) > 0),
                        "stock_quantity": p.get("quantity", 100),
                        "image_url": p.get("photos", [{}])[0].get("url") if p.get("photos") else None,
                        "source": "paystack",
                    })
                return products
            else:
                logger.error(f"Paystack products fetch failed: {res.text}")
                return []
