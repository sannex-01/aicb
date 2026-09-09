import json
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.order import Order
from app.core.logger import logger
from app.commerce.bumpa.client import BumpaClient


class FulfillmentManager:
    """Orchestrates order fulfillment by grouping the order's OWN items by
    fulfillment_type (physical/digital/service — see CatalogItem/cart line
    "fulfillment_type", threaded through since checkout) and dispatching
    each group through its own path, rather than the previous design of
    reading a single global settings.CATALOG_SOURCE and treating the whole
    order as one thing — a real problem for any business selling a mix of
    physical and digital items, or any order containing local-catalog items
    once a Bumpa/Paystack catalog is also connected.

    One Order/one payment throughout (see checkout.py's separate
    payment-ROUTING split, which is a different axis — Bumpa vs. other
    gateways, decided BEFORE payment) — this only splits what happens
    AFTER payment, purely for fulfillment dispatch.
    """

    @staticmethod
    async def dispatch_order(db: AsyncSession, order: Order) -> None:
        metadata = json.loads(order.metadata_json or "{}")
        if order.fulfillment_status in ("dispatched", "delivered", "delivered_digital", "shipped"):
            logger.info(f"Order {order.order_reference} already fulfilled ({order.fulfillment_status}). Skipping.")
            return

        try:
            items = json.loads(order.items_json)
        except Exception as e:
            logger.error(f"Failed to parse items for fulfillment on order {order.order_reference}: {e}")
            order.fulfillment_status = "failed"
            await db.commit()
            return

        from app.commerce.cart import CartManager
        groups = CartManager.group_by_fulfillment_type(items)

        group_results: Dict[str, Dict[str, Any]] = {}

        if groups["physical"]:
            group_results["physical"] = await FulfillmentManager._dispatch_physical(db, order, groups["physical"])
        if groups["digital"]:
            group_results["digital"] = await FulfillmentManager._dispatch_digital(db, order, groups["digital"])
        if groups["service"]:
            group_results["service"] = {"status": "manual", "detail": "Service item(s) — no automated dispatch. Merchant notified to follow up."}

        metadata["fulfillment_groups"] = group_results
        order.metadata_json = json.dumps(metadata)

        # Aggregate a single top-level status from the per-group results:
        # any real failure wins (needs attention), else "delivered_digital"
        # if that's the only/most-advanced thing that happened, else
        # whatever the physical group reported (dispatched/shipped),
        # else manual (service-only orders, or no groups matched at all).
        statuses = [g.get("status") for g in group_results.values()]
        if "failed" in statuses:
            order.fulfillment_status = "failed"
        elif "dispatched" in statuses or "shipped" in statuses:
            order.fulfillment_status = next(s for s in statuses if s in ("dispatched", "shipped"))
        elif "delivered_digital" in statuses:
            order.fulfillment_status = "delivered_digital"
        else:
            order.fulfillment_status = "manual"

        await db.commit()
        logger.info(f"Order {order.order_reference} fulfillment complete: {order.fulfillment_status} ({list(group_results.keys())})")

    @staticmethod
    async def _dispatch_physical(db: AsyncSession, order: Order, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Physical items only route to Bumpa when THOSE ITEMS actually came
        from Bumpa's catalog (source == "bumpa") — everything else
        (local-catalog physical items, or Paystack-catalog physical items)
        falls to the manual/internal path, since neither has a real
        fulfillment-push API today. Terminal Africa courier integration
        (a real automated dispatch for non-Bumpa physical items) isn't
        built yet — this is the honest gap that leaves, not a silent stub."""
        bumpa_items = [i for i in items if i.get("source") == "bumpa" and (i.get("external_id") or i.get("item_id"))]
        other_items = [i for i in items if i not in bumpa_items]

        if bumpa_items and not other_items:
            return await FulfillmentManager._push_to_bumpa(db, order, bumpa_items)

        if bumpa_items and other_items:
            # Mixed physical group (some Bumpa, some not) — dispatch what we
            # can to Bumpa, mark the rest manual, and be explicit about the
            # split rather than silently dropping one side.
            bumpa_result = await FulfillmentManager._push_to_bumpa(db, order, bumpa_items)
            return {
                "status": bumpa_result.get("status", "manual"),
                "detail": f"{len(bumpa_items)} item(s) pushed to Bumpa, {len(other_items)} item(s) require manual fulfillment (no courier integration configured yet).",
                "bumpa_response": bumpa_result.get("bumpa_response"),
            }

        return {
            "status": "manual",
            "detail": f"{len(other_items)} physical item(s) require manual fulfillment — no courier integration configured yet.",
        }

    @staticmethod
    async def _push_to_bumpa(db: AsyncSession, order: Order, bumpa_items: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            from app.services.store_connections import StoreConnectionService
            secret_key = await StoreConnectionService.get_effective_key(db, "bumpa")
            bumpa_client = BumpaClient(api_key=secret_key)

            formatted_items = [
                {
                    "product_id": item.get("external_id") or item.get("item_id"),
                    "quantity": item.get("quantity", 1),
                    "price": item.get("price", 0),
                }
                for item in bumpa_items
            ]

            name_parts = (order.customer_name or "Valued Customer").split(" ", 1)
            first_name = name_parts[0]
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            order_data = {
                "customer_first_name": first_name,
                "customer_last_name": last_name,
                "customer_phone": order.customer_phone or "00000000000",
                "customer_email": order.customer_email or "customer@example.com",
                "shipping_address": order.shipping_address or "TBD",
                "products": formatted_items,
                "payment_method": order.payment_gateway,
                "payment_status": "paid",
                "amount": sum(float(i.get("price", 0)) * int(i.get("quantity", 1)) for i in bumpa_items),
            }
            res = await bumpa_client.create_order(order_data)
            logger.info(f"Pushed {len(bumpa_items)} item(s) of order {order.order_reference} to Bumpa: {res}")
            return {"status": "dispatched", "detail": f"{len(bumpa_items)} item(s) pushed to Bumpa for fulfillment.", "bumpa_response": res}
        except Exception as e:
            logger.error(f"Failed to push order {order.order_reference} to Bumpa: {e}")
            return {"status": "failed", "detail": str(e)}

    @staticmethod
    async def _dispatch_digital(db: AsyncSession, order: Order, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delivers each digital item's asset link over the customer's own
        channel immediately — no waiting on a courier, no manual step.
        Looks up digital_asset_url fresh from the catalog (cart lines don't
        carry it — only fulfillment_type is threaded through checkout)
        since it's only needed at this final dispatch point, not earlier."""
        from app.commerce.catalog_provider import CatalogManager

        delivered_titles = []
        missing_assets = []
        for item in items:
            item_id = item.get("item_id")
            asset_url = None
            if item_id is not None:
                catalog_item = await CatalogManager.get_product_by_id(db, item_id)
                if catalog_item:
                    asset_url = catalog_item.digital_asset_url
            if asset_url:
                delivered_titles.append((item.get("title", "Item"), asset_url))
            else:
                missing_assets.append(item.get("title", "Item"))

        if delivered_titles:
            lines = ["📦 *Your digital item(s) are ready!*\n"]
            for title, url in delivered_titles:
                lines.append(f"• *{title}*\n  {url}")
            message = "\n".join(lines)
            try:
                if order.channel == "whatsapp":
                    from app.channels.whatsapp.client import WhatsAppClient
                    await WhatsAppClient().send_text_message(to=order.customer_identifier, body=message)
                elif order.channel == "telegram":
                    from app.channels.telegram.client import TelegramClient
                    await TelegramClient().send_message(chat_id=order.customer_identifier, text=message)
                # Widget: no push channel to deliver to outside the live
                # session — the asset link is still visible via Track
                # Order/My Purchases (order.metadata_json's group detail),
                # same as every other channel can also re-check later.
            except Exception as e:
                logger.error(f"Failed to deliver digital asset link for order {order.order_reference}: {e}")

        if missing_assets:
            logger.error(f"Order {order.order_reference} has digital item(s) with no digital_asset_url configured: {missing_assets}")

        if delivered_titles and not missing_assets:
            return {"status": "delivered_digital", "detail": f"{len(delivered_titles)} digital item(s) delivered."}
        elif delivered_titles and missing_assets:
            return {"status": "delivered_digital", "detail": f"{len(delivered_titles)} delivered; {len(missing_assets)} item(s) missing a configured asset: {', '.join(missing_assets)}."}
        else:
            return {"status": "failed", "detail": f"No digital_asset_url configured for: {', '.join(missing_assets)}."}
