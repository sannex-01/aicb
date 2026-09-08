import json
from typing import Any, Dict, List
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order
from app.core.logger import logger


class NotificationManager:
    """Fans a paid-order alert out across every merchant-alert channel a
    business has actually configured (Email, SMS, Telegram — WhatsApp
    template alerts aren't built yet, need a Meta-approved template first).
    Each channel is dispatched independently and best-effort: one channel's
    failure doesn't block another, matching the same resilience pattern
    FulfillmentManager already uses (log and move on, don't raise past
    this into the payment webhook that's calling it)."""

    @staticmethod
    def _build_message(order: Order) -> str:
        try:
            items = json.loads(order.items_json or "[]")
        except Exception:
            items = []
        items_summary = ", ".join(f"{i.get('quantity', 1)}x {i.get('title', 'Item')}" for i in items) or "Order items"

        lines = [
            f"🔔 New order paid — {order.order_reference}",
            f"Amount: {order.total_amount:,.2f} {order.currency}",
            f"Items: {items_summary}",
        ]
        if order.customer_name:
            lines.append(f"Customer: {order.customer_name}")
        if order.customer_phone:
            lines.append(f"Phone: {order.customer_phone}")
        if order.customer_email:
            lines.append(f"Email: {order.customer_email}")
        if order.shipping_address:
            lines.append(f"Delivery address: {order.shipping_address}")
        return "\n".join(lines)

    @staticmethod
    def _build_email_html(order: Order, message_text: str) -> str:
        body = message_text.replace("\n", "<br/>")
        return f"""
        <div style="font-family: sans-serif; padding: 24px; border: 1px solid #e5e7eb; border-radius: 8px; max-width: 500px;">
          <h2 style="color: #008060; margin-top: 0;">🎉 New Order Paid</h2>
          <p>{body}</p>
        </div>
        """

    @staticmethod
    async def notify_merchant_new_order(db: AsyncSession, order: Order) -> None:
        message = NotificationManager._build_message(order)

        # Email
        try:
            from app.services.alert_recipients import AlertRecipientsService
            from app.services.email import EmailService

            recipients = await AlertRecipientsService.get_recipients(db)
            for to_email in recipients.get("emails", []):
                try:
                    await EmailService.send_email(
                        db=db,
                        to_email=to_email,
                        subject=f"New order paid — {order.order_reference}",
                        html_content=NotificationManager._build_email_html(order, message),
                        text_content=message,
                    )
                except Exception as e:
                    logger.warning(f"Email order alert to {to_email} failed: {e}")
        except Exception as e:
            logger.warning(f"Email order alert channel skipped: {e}")

        # SMS
        try:
            from app.services.alert_recipients import AlertRecipientsService
            from app.services.sms import SMSService

            recipients = await AlertRecipientsService.get_recipients(db)
            for to_phone in recipients.get("phones", []):
                try:
                    await SMSService.send_sms(db=db, to_phone=to_phone, message=message[:300])
                except Exception as e:
                    logger.warning(f"SMS order alert to {to_phone} failed: {e}")
        except Exception as e:
            logger.warning(f"SMS order alert channel skipped: {e}")

        # Telegram
        try:
            from app.services.telegram_alerts import TelegramAlertService
            await TelegramAlertService.send_alert(db=db, message=message)
        except Exception as e:
            logger.warning(f"Telegram order alert failed: {e}")

        # WhatsApp template alerts: not built yet — needs a Meta-approved
        # message template before this can send anything real.
