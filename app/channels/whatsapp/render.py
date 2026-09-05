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
        """Returns {"text": str, "buttons": Optional[list], "list_sections": Optional[list],
        "carousel": Optional[dict]}.

        Product cards render as a free-form Interactive Media Carousel
        (swipeable image cards, one quick-reply button each) when there are
        2+ cards with images — Meta's carousel requires at least 2 cards and
        no template/catalog setup for this variant. Falls back to the
        interactive list message (no images, just tappable rows) when there
        are 0-1 images available, since a carousel of fewer than 2 cards
        isn't valid. Falls back further to quick-reply buttons when there
        are no cards at all.
        """
        text = resp.text + _url_buttons_as_text(resp.buttons)

        if resp.product_cards:
            cards_with_images = [c for c in resp.product_cards if c.image_url][:10]
            if len(cards_with_images) >= 2:
                carousel_cards = [
                    {
                        "image_url": card.image_url,
                        "caption": f"{card.title}\n{card.price:,.2f} {card.currency}"
                        + (f"\n{card.description}" if card.description else ""),
                        "button_id": card.buy_action_id,
                        "button_title": f"🛒 Buy {card.title}",
                    }
                    for card in cards_with_images
                ]
                return {
                    "text": text,
                    "buttons": None,
                    "list_sections": None,
                    "carousel": {"body": text, "cards": carousel_cards},
                }

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
                "carousel": None,
            }

        action_button_list = [b for b in resp.buttons if b.kind == "action"]
        if len(action_button_list) > 3:
            # WhatsApp's quick-reply buttons hard-cap at 3 — render as a list
            # message instead of silently truncating (_wa_buttons does [:3]).
            rows = [{"id": b.id, "title": b.title[:24]} for b in action_button_list[:10]]
            return {
                "text": text,
                "buttons": None,
                "list_sections": [{"title": "Options", "rows": rows}],
                "carousel": None,
            }

        action_buttons = _wa_buttons(resp.buttons)
        return {
            "text": text,
            "buttons": action_buttons if action_buttons else None,
            "list_sections": None,
            "carousel": None,
        }
