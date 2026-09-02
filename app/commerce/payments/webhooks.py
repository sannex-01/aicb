import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_paystack_signature,
    verify_flutterwave_hash,
    verify_stripe_signature,
)
from app.core.logger import logger
from app.models.order import Order, PaymentLog
from app.channels.whatsapp.client import WhatsAppClient
from app.channels.telegram.client import TelegramClient
from app.telemetry.client import telemetry_client

router = APIRouter(prefix="/webhooks/payments", tags=["Payment Webhooks"])


async def _notify_customer_payment_success(db: AsyncSession, order: Order) -> None:
    """Sends payment confirmation message to the customer over WhatsApp or Telegram."""
    msg = (
        f"🎉 *Payment Successful!*\n\n"
        f"We have received your payment of *{order.total_amount:,.2f} {order.currency}* for Order *{order.order_reference}*.\n\n"
        f"Your order is now being processed! Thank you for your business."
    )
    try:
        if order.channel == "whatsapp":
            await WhatsAppClient().send_text_message(to=order.customer_identifier, body=msg)
        elif order.channel == "telegram":
            await TelegramClient().send_message(chat_id=order.customer_identifier, text=msg)
    except Exception as e:
        logger.error(f"Failed to send payment receipt to customer: {e}")


# ==============================================================================
# Paystack Webhook
# ==============================================================================
@router.post("/paystack")
async def handle_paystack_webhook(
    request: Request,
    x_paystack_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    if not verify_paystack_signature(raw_body, x_paystack_signature):
        raise HTTPException(status_code=401, detail="Invalid Paystack signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    event_type = event_data.get("event")
    logger.info(f"Paystack webhook received: {event_type}")

    if event_type == "charge.success":
        data = event_data.get("data", {})
        reference = data.get("reference")
        amount = (data.get("amount") or 0) / 100.0
        currency = data.get("currency", "NGN")

        stmt = select(Order).where(Order.order_reference == reference)
        res = await db.execute(stmt)
        order = res.scalars().first()

        if order:
            order.status = "paid"
            order.payment_reference = reference
            order.payment_gateway = "paystack"

            # Create payment log
            payment_log = PaymentLog(
                order_reference=reference,
                gateway="paystack",
                gateway_reference=reference,
                amount=amount,
                currency=currency,
                status="success",
                payload_json=json.dumps(data),
            )
            db.add(payment_log)
            await db.commit()

            # Track telemetry
            telemetry_client.track(
                channel=order.channel,
                customer_id=order.customer_identifier,
                event="payment_success",
                amount=amount,
                status="success",
                metadata={"gateway": "paystack", "order_ref": reference},
            )

            # Sync receipt message to conversation transcript
            telemetry_client.sync_conversation(
                channel=order.channel,
                customer_id=order.customer_identifier,
                messages=[{
                    "role": "assistant",
                    "content": f"🎉 Payment Successful! Received {order.total_amount:,.2f} {order.currency} for Order {order.order_reference}.",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }],
            )

            await _notify_customer_payment_success(db, order)

    return {"status": "ok"}


# ==============================================================================
# Flutterwave Webhook
# ==============================================================================
@router.post("/flutterwave")
async def handle_flutterwave_webhook(
    request: Request,
    verif_hash: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    if not verify_flutterwave_hash(verif_hash):
        raise HTTPException(status_code=401, detail="Invalid Flutterwave hash")

    raw_body = await request.body()
    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    data = event_data.get("data", {})
    if data.get("status") == "successful":
        reference = data.get("tx_ref")
        amount = float(data.get("amount", 0))
        currency = data.get("currency", "NGN")

        stmt = select(Order).where(Order.order_reference == reference)
        res = await db.execute(stmt)
        order = res.scalars().first()

        if order:
            order.status = "paid"
            order.payment_reference = str(data.get("id"))
            order.payment_gateway = "flutterwave"

            payment_log = PaymentLog(
                order_reference=reference,
                gateway="flutterwave",
                gateway_reference=str(data.get("id")),
                amount=amount,
                currency=currency,
                status="success",
                payload_json=json.dumps(data),
            )
            db.add(payment_log)
            await db.commit()

            telemetry_client.track(
                channel=order.channel,
                customer_id=order.customer_identifier,
                event="payment_success",
                amount=amount,
                status="success",
                metadata={"gateway": "flutterwave", "order_ref": reference},
            )

            await _notify_customer_payment_success(db, order)

    return {"status": "ok"}


# ==============================================================================
# Monnify Webhook
# ==============================================================================
@router.post("/monnify")
async def handle_monnify_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    event_type = event_data.get("eventType")
    body = event_data.get("eventData", {})

    if event_type == "SUCCESSFUL_TRANSACTION":
        reference = body.get("paymentReference")
        amount = float(body.get("amountPaid", 0))
        currency = body.get("currency", "NGN")

        stmt = select(Order).where(Order.order_reference == reference)
        res = await db.execute(stmt)
        order = res.scalars().first()

        if order:
            order.status = "paid"
            order.payment_reference = body.get("transactionReference")
            order.payment_gateway = "monnify"

            payment_log = PaymentLog(
                order_reference=reference,
                gateway="monnify",
                gateway_reference=body.get("transactionReference", reference),
                amount=amount,
                currency=currency,
                status="success",
                payload_json=json.dumps(body),
            )
            db.add(payment_log)
            await db.commit()

            telemetry_client.track(
                channel=order.channel,
                customer_id=order.customer_identifier,
                event="payment_success",
                amount=amount,
                status="success",
                metadata={"gateway": "monnify", "order_ref": reference},
            )

            await _notify_customer_payment_success(db, order)

    return {"status": "ok"}


# ==============================================================================
# Stripe Webhook
# ==============================================================================
@router.post("/stripe")
async def handle_stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    raw_body = await request.body()
    if not verify_stripe_signature(raw_body, stripe_signature):
        raise HTTPException(status_code=401, detail="Invalid Stripe signature")

    try:
        event_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        return {"status": "ignored"}

    event_type = event_data.get("type")

    if event_type == "checkout.session.completed":
        session_obj = event_data.get("data", {}).get("object", {})
        reference = session_obj.get("client_reference_id") or session_obj.get("metadata", {}).get("order_reference")
        amount = (session_obj.get("amount_total") or 0) / 100.0
        currency = session_obj.get("currency", "usd").upper()

        if reference:
            stmt = select(Order).where(Order.order_reference == reference)
            res = await db.execute(stmt)
            order = res.scalars().first()

            if order:
                order.status = "paid"
                order.payment_reference = session_obj.get("id")
                order.payment_gateway = "stripe"

                payment_log = PaymentLog(
                    order_reference=reference,
                    gateway="stripe",
                    gateway_reference=session_obj.get("id"),
                    amount=amount,
                    currency=currency,
                    status="success",
                    payload_json=json.dumps(session_obj),
                )
                db.add(payment_log)
                await db.commit()

                telemetry_client.track(
                    channel=order.channel,
                    customer_id=order.customer_identifier,
                    event="payment_success",
                    amount=amount,
                    status="success",
                    metadata={"gateway": "stripe", "order_ref": reference},
                )

                await _notify_customer_payment_success(db, order)

    return {"status": "ok"}
