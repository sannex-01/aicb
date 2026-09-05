from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class ResponseButton(BaseModel):
    """A clickable button. 'action' round-trips its id into FlowEngine.handle_action;
    'url' opens an external link directly; 'inline_search' opens Telegram's
    bots/inline search UI in the current chat (switch_inline_query_current_chat)
    — Telegram-only, ignored by WhatsApp/widget renderers since neither has an
    equivalent."""
    id: str
    title: str
    kind: Literal["action", "url", "inline_search"] = "action"
    url: Optional[str] = None


class ProductCard(BaseModel):
    """A single catalog item rendered as a rich card (image + price + buy button)
    instead of flattened into text."""
    id: int
    title: str
    description: Optional[str] = None
    price: float
    currency: str = "NGN"
    image_url: Optional[str] = None
    buy_action_id: str


class BotResponse(BaseModel):
    """Channel-agnostic shape returned by FlowEngine.handle_action and AIOrchestrator.
    Every channel renderer (telegram/whatsapp/widget) consumes only this.

    Unlike the old {"type": "text"|"buttons", ...} dict, a single BotResponse can
    carry text, product cards, and buttons at once.
    """
    text: str = ""
    buttons: List[ResponseButton] = Field(default_factory=list)
    product_cards: List[ProductCard] = Field(default_factory=list)
    quick_replies: List[str] = Field(default_factory=list)
    checkout_url: Optional[str] = None
    end_session: bool = False
