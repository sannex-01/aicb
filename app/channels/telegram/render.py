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

        When product_cards are present, the caller should send them as one
        media-group album (via product_album below) instead of the flattened
        text — callers still get resp.text as a fallback/intro line.
        """
        return {
            "text": resp.text,
            "inline_keyboard": _inline_keyboard(resp.buttons),
            "photo_items": resp.product_cards,
        }

    @staticmethod
    def product_album(cards: List[ProductCard]) -> Dict[str, Any]:
        """Renders up to 10 ProductCards as one swipeable sendMediaGroup album,
        plus a follow-up text+inline-keyboard message for the buy actions.

        Telegram's media-group items can't carry per-item buttons, so the
        album (images + captions only) and the action buttons are two
        separate messages — the caller sends the album first, then this
        "actions" message right after, so the buttons still read as "for the
        album above" in the chat.
        """
        media_items = [
            {
                "photo_url": card.image_url,
                "caption": f"*{card.title}* — {card.price:,.2f} {card.currency}"
                + (f"\n_{card.description}_" if card.description else ""),
            }
            for card in cards[:10]
            if card.image_url
        ]

        # One "Buy" button per card, 2 per row, so a 10-product album still
        # fits in a reasonably short keyboard instead of one button per row.
        buy_buttons = [{"text": f"🛒 {card.title[:24]}", "callback_data": card.buy_action_id} for card in cards[:10]]
        rows = [buy_buttons[i:i + 2] for i in range(0, len(buy_buttons), 2)]
        rows.append([{"text": "🛒 View Cart", "callback_data": "flow_view_cart"}])

        return {
            "media_items": media_items,
            "actions_text": "👆 Swipe through the photos above, then tap below to buy:",
            "actions_keyboard": rows,
        }

    @staticmethod
    def inline_query_results(cards: List[ProductCard]) -> List[Dict[str, Any]]:
        """Renders ProductCards as Telegram inline-query results (bots/inline)
        for @botname <search> product search. Each result posts a normal
        photo+caption message into the chat carrying a real "Buy Now" inline
        button — same buy_action_id used everywhere else — rather than a
        bare action string, since inline-selected messages are sent as if
        the user typed them and would otherwise look like raw text."""
        results = []
        for card in cards[:50]:
            if not card.image_url:
                continue
            caption = f"*{card.title}* — {card.price:,.2f} {card.currency}"
            if card.description:
                caption += f"\n_{card.description}_"
            results.append(
                {
                    "type": "photo",
                    "id": f"prod_{card.id}",
                    "photo_url": card.image_url,
                    "thumbnail_url": card.image_url,
                    "title": card.title,
                    "description": f"{card.price:,.2f} {card.currency}",
                    "caption": caption,
                    "parse_mode": "Markdown",
                    "reply_markup": {
                        "inline_keyboard": [
                            [
                                {"text": "🛒 Buy Now", "callback_data": card.buy_action_id},
                                {"text": "🛒 View Cart", "callback_data": "flow_view_cart"},
                            ]
                        ]
                    },
                }
            )
        return results
