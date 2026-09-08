from typing import Dict, Any, Optional, List
from app.core.config import settings
from app.commerce.payments.paystack import PaystackClient
from app.commerce.payments.flutterwave import FlutterwaveClient
from app.commerce.payments.monnify import MonnifyClient
from app.commerce.payments.stripe import StripeClient
from app.core.logger import logger


class UnifiedPaymentManager:
    """Unified Gateway Factory for Paystack, Flutterwave, Monnify, Stripe, and Bumpa."""

    @staticmethod
    async def create_payment_link(
        amount: float,
        currency: str,
        customer_email: str,
        reference: str,
        gateway: Optional[str] = None,
        customer_name: Optional[str] = None,
        customer_phone: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        items: Optional[List[Dict[str, Any]]] = None,
        shipping_address: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        selected_gateway = (gateway or settings.DEFAULT_PAYMENT_GATEWAY).lower()

        logger.info(f"Initializing payment for {reference} ({amount} {currency}) via {selected_gateway.upper()}")

        if selected_gateway == "paystack":
            client = PaystackClient()
            return await client.initialize_payment(
                amount=amount,
                currency=currency,
                email=customer_email,
                reference=reference,
                metadata=metadata,
            )

        elif selected_gateway == "flutterwave":
            client = FlutterwaveClient()
            return await client.initialize_payment(
                amount=amount,
                currency=currency,
                email=customer_email,
                reference=reference,
                customer_name=customer_name,
                customer_phone=customer_phone,
                metadata=metadata,
            )

        elif selected_gateway == "monnify":
            client = MonnifyClient()
            return await client.initialize_payment(
                amount=amount,
                currency=currency,
                customer_name=customer_name or "Valued Customer",
                customer_email=customer_email,
                reference=reference,
            )

        elif selected_gateway == "stripe":
            client = StripeClient()
            return await client.initialize_payment(
                amount=amount,
                currency=currency,
                customer_email=customer_email,
                reference=reference,
                product_name=f"Order #{reference}",
                customer_name=customer_name,
                customer_phone=customer_phone,
            )

        elif selected_gateway == "bumpa":
            # Bumpa's checkout is fundamentally cart-based (real Bumpa
            # product_id/product_variation_id per line, via cart -> checkout
            # -> payment-intent), unlike every other gateway here which is a
            # flat amount -> link call. It needs actual line items, which
            # only the split-checkout caller (app/commerce/checkout.py)
            # provides — every item here MUST already be Bumpa-sourced
            # (filtered by the caller), this method does not itself check.
            if not items:
                raise ValueError(
                    "Bumpa checkout requires cart line items (product_id per "
                    "line) — none were provided. This gateway can't be used "
                    "with a flat amount-only payment link."
                )
            from app.services.store_connections import StoreConnectionService
            from app.core.database import AsyncSessionLocal
            from app.commerce.bumpa.client import BumpaClient

            async with AsyncSessionLocal() as db:
                secret_key = await StoreConnectionService.get_effective_key(db, "bumpa")
                public_key = await StoreConnectionService.get_effective_public_key(db, "bumpa")

            client = BumpaClient(api_key=secret_key, public_key=public_key)
            result = await client.checkout_via_bumpa(
                items=items,
                customer_email=customer_email,
                customer_name=customer_name,
                customer_phone=customer_phone,
                shipping_address=shipping_address,
            )
            return result

        else:
            raise ValueError(f"Unsupported payment gateway: {selected_gateway}")

    @staticmethod
    async def verify_payment(reference: str, gateway: Optional[str] = None) -> Dict[str, Any]:
        selected_gateway = (gateway or settings.DEFAULT_PAYMENT_GATEWAY).lower()

        if selected_gateway == "paystack":
            return await PaystackClient().verify_payment(reference)
        elif selected_gateway == "flutterwave":
            return await FlutterwaveClient().verify_payment(reference)
        elif selected_gateway == "monnify":
            return await MonnifyClient().verify_payment(reference)
        elif selected_gateway == "stripe":
            return await StripeClient().verify_payment(reference)
        else:
            raise ValueError(f"Unsupported payment gateway: {selected_gateway}")
