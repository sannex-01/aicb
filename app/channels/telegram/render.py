from typing import List, Dict, Any, Optional
from app.schemas.bot_response import BotResponse, ProductCard


# Main-menu button ids that should share one row (two columns) instead of
# each taking a full-width row of their own — purely a Telegram inline-
# keyboard layout choice; WhatsApp's quick-reply buttons are always
# full-width regardless, so this has no equivalent there.
_PAIRED_ROW_IDS = {
    frozenset({"flow_track_order", "flow_my_purchases"}),
}


def _inline_keyboard(buttons) -> Optional[List[List[Dict[str, str]]]]:
    if not buttons:
        return None
    rows: List[List[Dict[str, str]]] = []
    qty_row: List[Dict[str, str]] = []
    pending_pair: Optional[Dict[str, str]] = None
    ids_present = {b.id for b in buttons}

    def _make(b) -> Dict[str, str]:
        return {"text": b.title, "url": b.url} if (b.kind == "url" and b.url) else {"text": b.title, "callback_data": b.id}

    for b in buttons:
        btn_dict = _make(b)
        if b.id.startswith("qty_set_"):
            qty_row.append(btn_dict)
            if len(qty_row) >= 5:
                rows.append(qty_row)
                qty_row = []
            continue
        if qty_row:
            rows.append(qty_row)
            qty_row = []

        # If this button's id is one half of a known pair, and its partner
        # is also present in this response, hold it until the partner shows
        # up so both land on the same row together, in the order they were
        # given.
        paired_with = next((pair for pair in _PAIRED_ROW_IDS if b.id in pair and next(iter(pair - {b.id})) in ids_present), None)
        if paired_with:
            if pending_pair is not None:
                rows.append([pending_pair, btn_dict])
                pending_pair = None
            else:
                pending_pair = btn_dict
            continue

        rows.append([btn_dict])

    if pending_pair is not None:
        rows.append([pending_pair])
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
