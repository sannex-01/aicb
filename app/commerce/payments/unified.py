from typing import Dict, Any, Optional
from app.core.config import settings
from app.commerce.payments.paystack import PaystackClient
from app.commerce.payments.flutterwave import FlutterwaveClient
from app.commerce.payments.monnify import MonnifyClient
from app.commerce.payments.stripe import StripeClient
from app.core.logger import logger


class UnifiedPaymentManager:
    """Unified Gateway Factory for Paystack, Flutterwave, Monnify, and Stripe."""

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
