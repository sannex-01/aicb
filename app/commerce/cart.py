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
    async def add_item(
        db: AsyncSession,
        session: ConversationSession,
        item_id: Optional[int],
        title: str,
        price: float,
        quantity: int = 1,
        currency: str = "NGN",
    ) -> List[Dict[str, Any]]:
        state = MemoryManager.get_flow_state_data(session)
        cart = state.get("cart", [])

        # Check if item already exists in cart
        existing = None
        for entry in cart:
            if (item_id is not None and entry.get("item_id") == item_id) or (entry.get("title", "").lower() == title.lower()):
                existing = entry
                break

        if existing:
            existing["quantity"] = existing.get("quantity", 1) + quantity
        else:
            cart.append({
                "item_id": item_id,
                "title": title,
                "price": float(price),
                "quantity": int(quantity),
                "currency": currency,
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
            lines.append(f"{idx}. *{item.get('title')}* (x{item.get('quantity', 1)}) — {item_total:,.2f} {currency}")

        lines.append(f"\n💰 *Subtotal:* {subtotal:,.2f} {currency}")
        lines.append("🚚 *Delivery:* Calculated at checkout")
        lines.append("\nTap below to proceed with your order:")
        return "\n".join(lines)
