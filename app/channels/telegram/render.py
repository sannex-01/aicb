from typing import List, Dict, Any, Optional
from app.schemas.bot_response import BotResponse, ProductCard


def _inline_keyboard(buttons) -> Optional[List[List[Dict[str, str]]]]:
    if not buttons:
        return None
    rows = []
    qty_row = []
    for b in buttons:
        btn_dict = {"text": b.title, "url": b.url} if (b.kind == "url" and b.url) else {"text": b.title, "callback_data": b.id}
        if b.id.startswith("qty_set_"):
            qty_row.append(btn_dict)
            if len(qty_row) >= 5:
                rows.append(qty_row)
                qty_row = []
        else:
            if qty_row:
                rows.append(qty_row)
                qty_row = []
            rows.append([btn_dict])
    if qty_row:
        rows.append(qty_row)
    return rows


class TelegramRenderer:
    """Translates a channel-agnostic BotResponse into Telegram wire calls."""

    @staticmethod
    def render(resp: BotResponse) -> Dict[str, Any]:
        """Returns {"text": str, "inline_keyboard": Optional[list], "photo_items": List[ProductCard]}.

        When product_cards are present, the caller should send one photo per
        card (via TelegramClient.send_photo) instead of the flattened text —
        callers still get resp.text as a fallback/intro line.
        """
        return {
            "text": resp.text,
            "inline_keyboard": _inline_keyboard(resp.buttons),
            "photo_items": resp.product_cards,
        }

    @staticmethod
    def product_card_message(card: ProductCard) -> Dict[str, Any]:
        """Renders a single ProductCard into a Telegram sendPhoto-ready payload."""
        caption = f"*{card.title}* — {card.price:,.2f} {card.currency}"
        if card.description:
            caption += f"\n_{card.description}_"
        return {
            "caption": caption,
            "photo_url": card.image_url,
            "reply_markup": {
                "inline_keyboard": [
                    [
                        {"text": "🛒 Buy Now", "callback_data": card.buy_action_id},
                        {"text": "🛒 View Cart", "callback_data": "flow_view_cart"},
                    ]
                ]
            },
        }
