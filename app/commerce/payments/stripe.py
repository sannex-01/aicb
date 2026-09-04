from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings
from app.core.logger import logger

STRIPE_BASE_URL = "https://api.stripe.com/v1"


class StripeClient:
    """Stripe Checkout Sessions & Payment Intents Integration."""

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or settings.STRIPE_SECRET_KEY

    def _headers(self) -> Dict[str, str]:
        if not self.secret_key:
            raise ValueError("STRIPE_SECRET_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self.secret_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    async def initialize_payment(
        self,
        amount: float,
        currency: str,
        customer_email: str,
        reference: str,
        product_name: Optional[str] = None,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Creates a Stripe Checkout Session."""
        url = f"{STRIPE_BASE_URL}/checkout/sessions"
        amount_cents = int(round(amount * 100))

        data = {
            "payment_method_types[]": "card",
            "mode": "payment",
            "customer_email": customer_email,
            "client_reference_id": reference,
            "success_url": success_url or settings.STRIPE_SUCCESS_URL,
            "cancel_url": cancel_url or settings.STRIPE_CANCEL_URL,
            "line_items[0][price_data][currency]": currency.lower(),
            "line_items[0][price_data][unit_amount]": amount_cents,
            "line_items[0][price_data][product_data][name]": product_name or f"Order {reference}",
            "line_items[0][quantity]": 1,
            "metadata[order_reference]": reference,
        }
        # Stripe Checkout has no first-class name/phone fields — surface them
        # via metadata so they're visible in the dashboard, webhooks, and API.
        if customer_name:
            data["metadata[customer_name]"] = customer_name
        if customer_phone:
            data["metadata[customer_phone]"] = customer_phone

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, data=data, headers=self._headers())
            res_data = res.json()
            if res.status_code == 200 and "url" in res_data:
                return {
                    "checkout_url": res_data["url"],
                    "session_id": res_data["id"],
                    "reference": reference,
                }
            else:
                logger.error(f"Stripe session failed: {res.text}")
                error_msg = res_data.get("error", {}).get("message", "Stripe payment initialization failed")
                raise RuntimeError(error_msg)

    async def verify_payment(self, session_id: str) -> Dict[str, Any]:
        """Retrieves and verifies a Stripe Checkout Session."""
        url = f"{STRIPE_BASE_URL}/checkout/sessions/{session_id}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=self._headers())
            data = res.json()
            if res.status_code == 200:
                payment_status = data.get("payment_status")
                return {
                    "status": "success" if payment_status == "paid" else payment_status,
                    "amount": data.get("amount_total", 0) / 100.0,
                    "currency": data.get("currency"),
                    "reference": data.get("client_reference_id"),
                    "raw": data,
                }
            else:
                raise RuntimeError("Stripe session lookup failed")
