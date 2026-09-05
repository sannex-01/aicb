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
    product_row: List[Dict[str, str]] = []
    pending_pair: Optional[Dict[str, str]] = None
    ids_present = {b.id for b in buttons}

    def _make(b) -> Dict[str, Any]:
        if b.kind == "url" and b.url:
            return {"text": b.title, "url": b.url}
        if b.kind == "inline_search":
            # Opens Telegram's bots/inline search UI pre-scoped to this chat
            # (empty string = no pre-filled query text).
            return {"text": b.title, "switch_inline_query_current_chat": ""}
        return {"text": b.title, "callback_data": b.id}

    for b in buttons:
        btn_dict = _make(b)
        if b.id.startswith("qty_set_"):
            if product_row:
                rows.append(product_row)
                product_row = []
            qty_row.append(btn_dict)
            if len(qty_row) >= 5:
                rows.append(qty_row)
                qty_row = []
            continue
        if qty_row:
            rows.append(qty_row)
            qty_row = []

        if b.id.startswith("cart_add_"):
            product_row.append(btn_dict)
            if len(product_row) >= 2:
                rows.append(product_row)
                product_row = []
            continue
        if product_row:
            rows.append(product_row)
            product_row = []

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
    if product_row:
        rows.append(product_row)
    return rows


class TelegramRenderer:
    """Translates a channel-agnostic BotResponse into Telegram wire calls."""

    @staticmethod
    def render(resp: BotResponse) -> Dict[str, Any]:
        """Returns {"text": str, "inline_keyboard": Optional[list], "photo_items": List[ProductCard]}.

        Only product cards with valid image_urls are included in photo_items so
        callers never attempt to render empty/phantom media albums.
        """
        valid_photos = [card for card in resp.product_cards if card.image_url]
        return {
            "text": resp.text,
            "inline_keyboard": _inline_keyboard(resp.buttons),
            "photo_items": valid_photos,
        }

    @staticmethod
    def product_album(cards: List[ProductCard]) -> Dict[str, Any]:
        """Renders up to 10 ProductCards with images as one swipeable sendMediaGroup album."""
        media_items = [
            {
                "photo_url": card.image_url,
                "caption": f"*{card.title}* — {card.price:,.2f} {card.currency}"
                + (f"\n_{card.description}_" if card.description else ""),
            }
            for card in cards[:10]
            if card.image_url
        ]
        return {
            "media_items": media_items,
        }

    @staticmethod
    def inline_query_results(cards: List[ProductCard]) -> List[Dict[str, Any]]:
        """Renders ProductCards as Telegram inline-query results (bots/inline)
        for @botname <search> product search. Works reliably for all products
        (whether images exist or not) using Telegram's article format with
        rich inline Buy Now & View Cart buttons."""
        results = []
        for card in cards[:50]:
            caption = f"🛍️ *{card.title}* — {card.price:,.2f} {card.currency}"
            if card.description:
                caption += f"\n_{card.description}_"
            caption += "\n\n👉 Tap below to buy or view your cart:"

            item_dict: Dict[str, Any] = {
                "type": "article",
                "id": f"prod_{card.id}",
                "title": f"{card.title} — {card.price:,.2f} {card.currency}",
                "description": card.description or f"Price: {card.price:,.2f} {card.currency}",
                "input_message_content": {
                    "message_text": caption,
                    "parse_mode": "Markdown",
                },
                "reply_markup": {
                    "inline_keyboard": [
                        [
                            {"text": f"🛒 Buy {card.title[:20]}", "callback_data": card.buy_action_id},
                            {"text": "🛒 View Cart", "callback_data": "flow_view_cart"},
                        ]
                    ]
                },
            }
            if card.image_url:
                item_dict["thumbnail_url"] = card.image_url
                item_dict["thumb_width"] = 64
                item_dict["thumb_height"] = 64

            results.append(item_dict)
        return results
