import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order
from app.core.logger import logger
from app.commerce.bumpa.client import BumpaClient
from app.core.config import settings

class FulfillmentManager:
    """Orchestrates order fulfillment based on the product's origin source."""

    @staticmethod
    async def dispatch_order(db: AsyncSession, order: Order) -> None:
        """Analyzes order items and routes them to their upstream fulfillment systems."""

        # Idempotency check: Skip if already fulfilled
        import json
        metadata = json.loads(order.metadata_json or "{}")
        if metadata.get("fulfillment_status") == "dispatched":
            logger.info(f"Order {order.order_reference} already dispatched for fulfillment. Skipping.")
            return

        try:
            items = json.loads(order.items_json)
        except Exception as e:
            logger.error(f"Failed to parse items for fulfillment on order {order.order_reference}: {e}")
            return

        if settings.CATALOG_SOURCE.lower() == "bumpa":
            # Push order to bumpa
            try:
                # Format items for bumpa
                bumpa_items = []
                for item in items:
                    # Depending on how bumpa expects it:
                    # Usually needs product_id, quantity, etc.
                    bumpa_items.append({
                        "product_id": item.get("external_id") or item.get("item_id"),
                        "quantity": item.get("quantity", 1),
                        "price": item.get("price", 0)
                    })

                bumpa_client = BumpaClient()

                # Split name into first and last
                name_parts = (order.customer_name or "Valued Customer").split(" ", 1)
                first_name = name_parts[0]
                last_name = name_parts[1] if len(name_parts) > 1 else ""

                order_data = {
                    "customer_first_name": first_name,
                    "customer_last_name": last_name,
                    "customer_phone": order.customer_phone or "00000000000",
                    "customer_email": order.customer_email or "customer@example.com",
                    "shipping_address": order.shipping_address or "TBD",
                    "products": bumpa_items,
                    "payment_method": order.payment_gateway,
                    "payment_status": "paid",
                    "amount": order.total_amount
                }

                res = await bumpa_client.create_order(order_data)
                logger.info(f"Pushed order {order.order_reference} to Bumpa: {res}")

                # Mark as dispatched
                metadata["fulfillment_status"] = "dispatched"
                metadata["bumpa_response"] = res
                order.metadata_json = json.dumps(metadata)
                await db.commit()

            except Exception as e:
                logger.error(f"Failed to push order {order.order_reference} to Bumpa: {e}")
                # Record failure for retry
                metadata["fulfillment_status"] = "failed"
                metadata["fulfillment_error"] = str(e)
                order.metadata_json = json.dumps(metadata)
                await db.commit()
        elif settings.CATALOG_SOURCE.lower() in ("paystack", "local"):
            # For pure digital or local products without native fulfillment APIs (like Paystack storefronts
            # or manual DB entries), trigger the internal fallback logic.
            logger.info(f"Order {order.order_reference} requires internal/manual fulfillment dispatch.")

            metadata["fulfillment_status"] = "dispatched"
            metadata["fulfillment_method"] = "manual"
            order.metadata_json = json.dumps(metadata)
            await db.commit()
