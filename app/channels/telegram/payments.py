from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings
from app.core.logger import logger


class TelegramPaymentsHandler:
    """Handles Telegram In-App Payments & Invoices."""

    @staticmethod
    def build_labeled_prices(amount: float, currency: str = "NGN") -> List[Dict[str, Any]]:
        # Telegram payments use smallest currency unit (e.g. kobo/cents)
        amount_units = int(round(amount * 100))
        return [{"label": "Order Total", "amount": amount_units}]
