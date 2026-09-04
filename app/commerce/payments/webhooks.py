import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Header, HTTPException, Depends
from fastapi.responses import HTMLResponse
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
# Paystack Callback (Browser Redirect after Payment)
# ==============================================================================
@router.get("/paystack/callback")
async def handle_paystack_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Paystack redirects the customer's browser here after checkout.
    We immediately verify payment and update the order status.
    Returns an HTML page that auto-redirects to the Telegram bot.
    """
    from app.commerce.payments.paystack import PaystackClient

    reference = request.query_params.get("trxref") or request.query_params.get("reference")
    if not reference:
        return HTMLResponse(
            content=_callback_html("❌ Missing Reference", "No payment reference was provided.", redirect_url=None),
            status_code=400,
        )

    # Check if order exists
    stmt = select(Order).where(Order.order_reference == reference)
    res = await db.execute(stmt)
    order = res.scalars().first()

    if not order:
        return HTMLResponse(
            content=_callback_html("❌ Order Not Found", f"No order found for reference {reference}.", redirect_url=None),
            status_code=404,
        )

    # Already paid? Show confirmation directly
    if order.status == "paid":
        redirect_url = _get_bot_redirect_url(order)
        return HTMLResponse(
            content=_callback_html(
                "✅ Payment Already Confirmed",
                f"Your payment of {order.total_amount:,.2f} {order.currency} for Order {order.order_reference} was already confirmed!",
                redirect_url=redirect_url,
            ),
        )

    # Verify with Paystack API
    try:
        result = await PaystackClient().verify_payment(reference)
        if result.get("status") == "success":
            order.status = "paid"
            order.payment_reference = reference
            order.payment_gateway = "paystack"

            payment_log = PaymentLog(
                order_reference=reference,
                gateway="paystack",
                gateway_reference=reference,
                amount=result.get("amount", 0),
                currency=result.get("currency", "NGN"),
                status="success",
                payload_json=json.dumps(result.get("raw", {})),
            )
            db.add(payment_log)
            await db.commit()

            telemetry_client.track(
                channel=order.channel,
                customer_id=order.customer_identifier,
                event="payment_success",
                amount=result.get("amount", 0),
                status="success",
                metadata={"gateway": "paystack", "order_ref": reference, "source": "callback"},
            )

            await _notify_customer_payment_success(db, order)

            redirect_url = _get_bot_redirect_url(order)
            return HTMLResponse(
                content=_callback_html(
                    "🎉 Payment Successful!",
                    f"Your payment of {order.total_amount:,.2f} {order.currency} for Order {order.order_reference} has been confirmed.",
                    redirect_url=redirect_url,
                ),
            )
        else:
            return HTMLResponse(
                content=_callback_html(
                    "⏳ Payment Pending",
                    f"Your payment for Order {order.order_reference} has not been confirmed yet. Please wait a moment and try again.",
                    redirect_url=None,
                ),
            )
    except Exception as e:
        logger.error(f"Paystack callback verification error: {e}")
        return HTMLResponse(
            content=_callback_html(
                "⚠️ Verification Error",
                "We couldn't verify your payment right now. Don't worry — if you completed payment, our system will confirm it shortly via webhook.",
                redirect_url=None,
            ),
        )


def _get_bot_redirect_url(order: Order) -> str:
    """Returns a redirect URL to send the customer back to the bot chat."""
    if order.channel == "telegram" and settings.TELEGRAM_BOT_USERNAME:
        return f"https://t.me/{settings.TELEGRAM_BOT_USERNAME.lstrip('@')}"
    return ""


def _callback_html(title: str, message: str, redirect_url: str | None) -> str:
    """Generates a minimal, branded HTML page for the payment callback."""
    redirect_meta = ""
    redirect_link = ""
    if redirect_url:
        redirect_meta = f'<meta http-equiv="refresh" content="4;url={redirect_url}">'
        redirect_link = f'<a href="{redirect_url}" style="display:inline-block;margin-top:20px;padding:12px 28px;background:#008060;color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">Return to Chat →</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {redirect_meta}
    <title>{title}</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; }}
        body {{ font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; background:#0a0a0a; color:#e5e5e5; display:flex; align-items:center; justify-content:center; min-height:100vh; padding:20px; }}
        .card {{ background:#1a1a1a; border:1px solid #333; border-radius:16px; padding:40px; max-width:420px; width:100%; text-align:center; }}
        h1 {{ font-size:24px; margin-bottom:12px; }}
        p {{ font-size:14px; color:#999; line-height:1.6; }}
        .redirect-note {{ font-size:12px; color:#666; margin-top:16px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>{title}</h1>
        <p>{message}</p>
        {redirect_link}
        {f'<p class="redirect-note">Redirecting you back to the chat in a few seconds...</p>' if redirect_url else ''}
    </div>
</body>
</html>"""



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
