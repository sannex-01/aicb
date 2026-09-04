from typing import List, Dict, Any, Optional
from app.schemas.bot_response import BotResponse


def _wa_buttons(buttons) -> List[Dict[str, str]]:
    """WhatsApp quick-reply buttons only support round-tripping an id — a
    'url' button has no native equivalent, so it's appended to the text body
    instead (see WhatsAppRenderer.render)."""
    return [{"id": b.id, "title": b.title} for b in buttons if b.kind == "action"][:3]


def _url_buttons_as_text(buttons) -> str:
    lines = [f"*{b.title}*: {b.url}" for b in buttons if b.kind == "url" and b.url]
    return ("\n\n" + "\n".join(lines)) if lines else ""


class WhatsAppRenderer:
    """Translates a channel-agnostic BotResponse into WhatsApp Cloud API wire calls."""

    @staticmethod
    def render(resp: BotResponse) -> Dict[str, Any]:
        """Returns {"text": str, "buttons": Optional[list], "list_sections": Optional[list]}.

        Product cards render as a single interactive list message (up to 10
        rows) rather than N separate image messages — WhatsApp's own
        interactive-message constraints mean an image message can't carry a
        reply button, and a wall of separate photos is worse UX than one
        list here. Falls back to quick-reply buttons when there are no cards.
        """
        text = resp.text + _url_buttons_as_text(resp.buttons)

        if resp.product_cards:
            rows = [
                {
                    "id": card.buy_action_id,
                    "title": card.title[:24],
                    "description": f"{card.price:,.2f} {card.currency}"[:72],
                }
                for card in resp.product_cards[:10]
            ]
            return {
                "text": text,
                "buttons": None,
                "list_sections": [{"title": "Available Products", "rows": rows}],
            }

        action_buttons = _wa_buttons(resp.buttons)
        return {
            "text": text,
            "buttons": action_buttons if action_buttons else None,
            "list_sections": None,
        }
