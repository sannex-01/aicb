import json
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import ConversationSession
from app.models.catalog import CatalogItem
from app.ai.memory import MemoryManager
from app.core.logger import logger


class CartManager:
    """Manages conversational shopping cart stored in session.state_data without LLM tokens."""

    @staticmethod
    def get_cart(session: ConversationSession) -> List[Dict[str, Any]]:
        state = MemoryManager.get_flow_state_data(session)
        return state.get("cart", [])

    @staticmethod
    def calculate_subtotal(cart: List[Dict[str, Any]]) -> float:
        return sum(float(item.get("price", 0.0)) * int(item.get("quantity", 1)) for item in cart)

    @staticmethod
    def cart_requires_shipping(cart: List[Dict[str, Any]]) -> bool:
        """True if ANY line needs delivery — address collection is gated on
        this, not on every single item. Missing the key (older cart entries
        added before this flag existed, or entries built by paths that don't
        set it) defaults to True — the safer assumption for a physical-goods
        catalog, matching CatalogItem.requires_shipping's own default."""
        return any(item.get("requires_shipping", True) for item in cart)

    @staticmethod
    def group_by_fulfillment_type(cart: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Splits cart lines into {"physical": [...], "digital": [...],
        "service": [...]} — used by FulfillmentManager to dispatch each
        group through its own path after a single payment (one Order/one
        charge; only the FULFILLMENT step is split, not the checkout
        itself — see checkout.py's separate payment-routing split for
        Bumpa, a different axis entirely). Missing the key defaults to
        "physical", matching CatalogItem.fulfillment_type's own default."""
        groups: Dict[str, List[Dict[str, Any]]] = {"physical": [], "digital": [], "service": []}
        for item in cart:
            ft = item.get("fulfillment_type") or "physical"
            groups.setdefault(ft, []).append(item)
        return groups

    @staticmethod
    async def add_item(
        db: AsyncSession,
        session: ConversationSession,
        item_id: Optional[int],
        title: str,
        price: float,
        quantity: int = 1,
        currency: str = "NGN",
        external_id: Optional[str] = None,
        variant_id: Optional[int] = None,
        variant_name: Optional[str] = None,
        source: Optional[str] = None,
        variant_external_id: Optional[str] = None,
        requires_shipping: bool = True,
        fulfillment_type: str = "physical",
    ) -> List[Dict[str, Any]]:
        state = MemoryManager.get_flow_state_data(session)
        cart = state.get("cart", [])

        # Check if this exact item+variant combination already exists in
        # cart. Two different variants of the same base product (same
        # item_id, different variant_id) are separate cart lines, not
        # merged — a customer buying a Small and a Large should see both,
        # not a single "2x" line that loses which size is which.
        existing = None
        for entry in cart:
            same_item = (item_id is not None and entry.get("item_id") == item_id) or (entry.get("title", "").lower() == title.lower())
            same_variant = entry.get("variant_id") == variant_id
            if same_item and same_variant:
                existing = entry
                break

        if existing:
            existing["quantity"] = existing.get("quantity", 1) + quantity
        else:
            cart.append({
                "item_id": item_id,
                "external_id": external_id,
                "title": title,
                "price": float(price),
                "quantity": int(quantity),
                "currency": currency,
                "variant_id": variant_id,
                "variant_name": variant_name,
                "source": source,
                "variant_external_id": variant_external_id,
                "requires_shipping": requires_shipping,
                "fulfillment_type": fulfillment_type,
            })

        state["cart"] = cart
        await MemoryManager.update_flow_state(
            db, session,
            active_flow=session.active_flow,
            current_step=session.current_step,
            state_data=state,
        )
        return cart

    @staticmethod
    async def set_item_quantity(
        db: AsyncSession,
        session: ConversationSession,
        item_id: Optional[int],
        quantity: int,
        title: Optional[str] = None,
        price: Optional[float] = None,
        currency: str = "NGN",
    ) -> List[Dict[str, Any]]:
        state = MemoryManager.get_flow_state_data(session)
        cart = state.get("cart", [])

        found = False
        new_cart = []
        for entry in cart:
            is_match = (item_id is not None and entry.get("item_id") == item_id) or (
                title and entry.get("title", "").lower() == title.lower()
            )
            if is_match:
                found = True
                if quantity > 0:
                    entry["quantity"] = int(quantity)
                    new_cart.append(entry)
            else:
                new_cart.append(entry)

        if not found and quantity > 0 and (title or item_id is not None):
            new_cart.append({
                "item_id": item_id,
                "title": title or f"Item #{item_id}",
                "price": float(price or 0.0),
                "quantity": int(quantity),
                "currency": currency,
            })

        state["cart"] = new_cart
        await MemoryManager.update_flow_state(
            db, session,
            active_flow=session.active_flow,
            current_step=session.current_step,
            state_data=state,
        )
        return new_cart

    @staticmethod
    async def remove_item(
        db: AsyncSession,
        session: ConversationSession,
        item_id: Optional[int] = None,
        title: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        state = MemoryManager.get_flow_state_data(session)
        cart = state.get("cart", [])

        updated_cart = []
        for entry in cart:
            if item_id is not None and entry.get("item_id") == item_id:
                continue
            if title and entry.get("title", "").lower() == title.lower():
                continue
            updated_cart.append(entry)

        state["cart"] = updated_cart
        await MemoryManager.update_flow_state(
            db, session,
            active_flow=session.active_flow,
            current_step=session.current_step,
            state_data=state,
        )
        return updated_cart

    @staticmethod
    async def clear_cart(db: AsyncSession, session: ConversationSession) -> None:
        state = MemoryManager.get_flow_state_data(session)
        state["cart"] = []
        await MemoryManager.update_flow_state(
            db, session,
            active_flow=session.active_flow,
            current_step=session.current_step,
            state_data=state,
        )

    @staticmethod
    def format_cart_message(cart: List[Dict[str, Any]]) -> str:
        if not cart:
            return "🛒 *Your Shopping Cart is Empty!*\n\nBrowse our catalog to select items you love."

        subtotal = CartManager.calculate_subtotal(cart)
        currency = cart[0].get("currency", "NGN") if cart else "NGN"

        lines = ["🛒 *Your Shopping Cart:*\n"]
        for idx, item in enumerate(cart, 1):
            item_total = float(item.get("price", 0.0)) * int(item.get("quantity", 1))
            variant_suffix = f" ({item['variant_name']})" if item.get("variant_name") else ""
            lines.append(f"{idx}. *{item.get('title')}{variant_suffix}* (x{item.get('quantity', 1)}) — {item_total:,.2f} {currency}")

        lines.append(f"\n💰 *Subtotal:* {subtotal:,.2f} {currency}")
        lines.append("🚚 *Delivery:* Calculated at checkout")
        lines.append("\nTap below to proceed with your order:")
        return "\n".join(lines)
