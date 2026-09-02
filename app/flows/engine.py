import json
import uuid
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import ConversationSession
from app.models.order import Order
from app.ai.memory import MemoryManager
from app.commerce.catalog_provider import CatalogManager
from app.commerce.cart import CartManager
from app.commerce.payments.unified import UnifiedPaymentManager
from app.channels.slack.fallback import get_support_contact_message
from app.flows.definitions import (
    MAIN_MENU_BUTTONS,
    CART_BUTTONS,
    CART_EMPTY_BUTTONS,
    get_main_menu_text,
)
from app.core.logger import logger


class FlowEngine:
    """State machine for deterministic interactive buttons and step-by-step flows (0 LLM Tokens)."""

    @staticmethod
    async def handle_action(
        db: AsyncSession,
        session: ConversationSession,
        action_id: str,
        user_input: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Handles interactive button callbacks and progression."""
        action = action_id.lower().strip()
        logger.info(f"Flow engine processing action: {action}")

        # 1. Main Menu Trigger
        if action in ["flow_main_menu", "/start", "menu", "start"]:
            await MemoryManager.update_flow_state(db, session, active_flow="main_menu", current_step="root")
            return {
                "type": "buttons",
                "text": get_main_menu_text(),
                "buttons": MAIN_MENU_BUTTONS,
            }

        # 2. Browse Products Flow
        elif action == "flow_browse_catalog":
            products = await CatalogManager.search_products(db, limit=6)
            if not products:
                return {
                    "type": "buttons",
                    "text": "🛍️ Our catalog is currently being updated. Please check back shortly!",
                    "buttons": MAIN_MENU_BUTTONS,
                }

            product_lines = []
            buttons = []
            for p in products:
                product_lines.append(f"• *{p.title}* — {p.price:,.2f} {p.currency}\n  _{p.description or 'In stock'}_\n  👉 Tap below to add to cart")
                buttons.append({"id": f"cart_add_{p.id}", "title": f"🛒 Buy {p.title[:20]}"})

            buttons.append({"id": "flow_view_cart", "title": "🛒 View Cart"})
            buttons.append({"id": "flow_main_menu", "title": "🏠 Menu"})

            reply_text = "🛍️ *Available Products & Services:*\n\n" + "\n\n".join(product_lines)

            await MemoryManager.update_flow_state(db, session, active_flow="catalog", current_step="viewing")
            return {
                "type": "buttons",
                "text": reply_text,
                "buttons": buttons,
            }

        # 3. Add to Cart via Button Click (e.g. "cart_add_1")
        elif action.startswith("cart_add_"):
            item_id_str = action.replace("cart_add_", "")
            product = None
            if item_id_str.isdigit():
                product = await CatalogManager.get_product_by_id(db, int(item_id_str))

            if product:
                cart = await CartManager.add_item(
                    db=db,
                    session=session,
                    item_id=product.id,
                    title=product.title,
                    price=product.price,
                    quantity=1,
                    currency=product.currency,
                )
                cart_msg = CartManager.format_cart_message(cart)
                return {
                    "type": "buttons",
                    "text": f"✅ *Added 1x {product.title} to your cart!*\n\n{cart_msg}",
                    "buttons": CART_BUTTONS,
                }
            else:
                return {
                    "type": "buttons",
                    "text": "Could not find that product. Please select from our catalog:",
                    "buttons": MAIN_MENU_BUTTONS,
                }

        # 4. View Cart
        elif action in ["flow_view_cart", "cart", "view_cart"]:
            cart = CartManager.get_cart(session)
            if not cart:
                return {
                    "type": "buttons",
                    "text": "🛒 *Your Shopping Cart is Empty!*\n\nBrowse our products to start adding items.",
                    "buttons": CART_EMPTY_BUTTONS,
                }
            return {
                "type": "buttons",
                "text": CartManager.format_cart_message(cart),
                "buttons": CART_BUTTONS,
            }

        # 5. Clear Cart
        elif action in ["flow_clear_cart", "clear_cart"]:
            await CartManager.clear_cart(db, session)
            return {
                "type": "buttons",
                "text": "🗑️ *Your cart has been cleared.*",
                "buttons": CART_EMPTY_BUTTONS,
            }

        # 6. Checkout Flow (Zero LLM Tokens)
        elif action in ["flow_checkout", "checkout"]:
            cart = CartManager.get_cart(session)
            if not cart:
                return {
                    "type": "buttons",
                    "text": "🛒 *Your cart is currently empty!* Please add items first before checking out.",
                    "buttons": CART_EMPTY_BUTTONS,
                }

            total_amount = CartManager.calculate_subtotal(cart)
            currency = cart[0].get("currency", "NGN") if cart else "NGN"
            order_ref = f"ORD-{uuid.uuid4().hex[:8].upper()}"

            # Create order in database
            order = Order(
                order_reference=order_ref,
                customer_identifier=session.customer_identifier,
                channel=session.channel,
                items_json=json.dumps(cart),
                total_amount=total_amount,
                currency=currency,
                status="pending",
                payment_gateway="paystack",
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)

            # Generate Paystack checkout link
            email = f"customer_{session.customer_identifier.replace('+', '')}@example.com"
            payment_res = await UnifiedPaymentManager.create_payment_link(
                amount=total_amount,
                currency=currency,
                customer_email=email,
                reference=order_ref,
                gateway="paystack",
                metadata={
                    "channel": session.channel,
                    "customer_id": session.customer_identifier,
                    "order_reference": order_ref,
                },
            )
            checkout_url = payment_res.get("checkout_url")
            order.checkout_url = checkout_url
            await db.commit()

            # Empty the cart now that order is generated
            await CartManager.clear_cart(db, session)

            # Track payment initiation telemetry even if not yet completed
            from app.telemetry.client import telemetry_client
            telemetry_client.track(
                channel=session.channel,
                customer_id=session.customer_identifier,
                event="payment_initiated",
                status="pending",
                amount=total_amount,
                metadata={
                    "order_reference": order_ref,
                    "currency": currency,
                    "checkout_url": checkout_url,
                },
            )

            order_summary = [
                f"🎉 *Order #{order_ref} Created!*",
                f"\n💵 *Total to Pay:* {total_amount:,.2f} {currency}",
                f"\n👉 *Pay Now via Paystack:*",
                f"{checkout_url}",
                f"\n_We will notify you immediately once payment is confirmed!_",
            ]
            return {
                "type": "text",
                "text": "\n".join(order_summary),
            }

        # 7. Track Order Flow
        elif action == "flow_track_order" or session.active_flow == "track_order" or action_id.upper().startswith("ORD-"):
            ref_to_check = (user_input or action_id).strip().upper()
            if ref_to_check.startswith("ORD-"):
                stmt = select(Order).where(Order.order_reference == ref_to_check)
                res = await db.execute(stmt)
                order = res.scalars().first()
                await MemoryManager.update_flow_state(db, session, active_flow=None, current_step=None)
                if order:
                    status_emoji = "✅" if order.status == "paid" else "⏳" if order.status == "pending" else "📦"
                    items_detail = ""
                    try:
                        parsed_items = json.loads(order.items_json) if order.items_json else []
                        items_detail = "\n" + "\n".join([f"  • {it.get('quantity', 1)}x {it.get('title', 'Item')} ({it.get('price', 0):,.2f} {order.currency})" for it in parsed_items])
                    except Exception:
                        pass

                    return {
                        "type": "buttons",
                        "text": (
                            f"{status_emoji} *Order #{order.order_reference} Details*\n\n"
                            f"• *Status:* {order.status.upper()}\n"
                            f"• *Total:* {order.total_amount:,.2f} {order.currency}\n"
                            f"• *Items:*{items_detail}\n"
                            f"• *Date:* {order.created_at.strftime('%Y-%m-%d %H:%M UTC') if order.created_at else 'Recent'}"
                        ),
                        "buttons": MAIN_MENU_BUTTONS,
                    }
                else:
                    return {
                        "type": "buttons",
                        "text": f"❌ No order found matching reference `{ref_to_check}`. Please double check your order number or tap below:",
                        "buttons": MAIN_MENU_BUTTONS,
                    }

            await MemoryManager.update_flow_state(db, session, active_flow="track_order", current_step="awaiting_reference")
            return {
                "type": "text",
                "text": "📦 Please reply with your *Order Reference* (e.g. `ORD-AB12CD34`) to check your order status.",
            }

        # 8. Talk to Human / Contact Support
        elif action == "flow_contact_support":
            support_msg = get_support_contact_message()
            await MemoryManager.update_flow_state(db, session, active_flow=None, current_step=None)
            return {
                "type": "text",
                "text": support_msg,
            }

        return {
            "type": "text",
            "text": "How else can we assist you today?",
        }
