from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import ConversationSession
from app.ai.memory import MemoryManager
from app.commerce.catalog_provider import CatalogManager
from app.channels.slack.fallback import get_support_contact_message
from app.flows.definitions import MAIN_MENU_BUTTONS, get_main_menu_text
from app.core.logger import logger


class FlowEngine:
    """State machine for deterministic interactive buttons and step-by-step flows."""

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
            products = await CatalogManager.search_products(db, limit=5)
            if not products:
                return {
                    "type": "text",
                    "text": "🛍️ Our catalog is currently being updated. Please check back shortly!",
                }

            product_lines = []
            for p in products:
                product_lines.append(f"• *{p.title}* - {p.price:,.2f} {p.currency}\n  {p.description or ''}")

            reply_text = "🛍️ *Available Products & Services:*\n\n" + "\n\n".join(product_lines)
            reply_text += "\n\n_To purchase any product, just type its name or tell us what you'd like to order!_"

            await MemoryManager.update_flow_state(db, session, active_flow="catalog", current_step="viewing")
            return {
                "type": "text",
                "text": reply_text,
            }

        # 3. Track Order Flow
        elif action == "flow_track_order":
            await MemoryManager.update_flow_state(db, session, active_flow="track_order", current_step="awaiting_reference")
            return {
                "type": "text",
                "text": "📦 Please reply with your *Order Reference* (e.g. `ORD-AB12CD34`) to check your order status.",
            }

        # 4. Talk to Human / Contact Support
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
