from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import logger

GRAPH_API_VERSION = "v21.0"


class WhatsAppClient:
    """Meta WhatsApp Cloud API Client."""

    def __init__(self, token: Optional[str] = None, phone_number_id: Optional[str] = None):
        self.token = token or settings.META_WHATSAPP_TOKEN
        self.phone_number_id = phone_number_id or settings.META_PHONE_NUMBER_ID

    def _url(self) -> str:
        if not self.phone_number_id:
            logger.warning("META_PHONE_NUMBER_ID is not configured. Outgoing message skipped.")
            return ""
        return f"https://graph.facebook.com/{GRAPH_API_VERSION}/{self.phone_number_id}/messages"

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            logger.warning("META_WHATSAPP_TOKEN is not configured.")
            return {}
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self._url()
        headers = self._headers()
        if not url or not headers:
            logger.info(f"[DEV MOCK] WhatsApp message payload: {payload}")
            return {"status": "mocked", "payload": payload}

        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            data = res.json()
            if res.status_code not in [200, 201]:
                logger.error(f"WhatsApp message send error: {res.status_code} - {res.text}")
            return data

    async def send_text_message(self, to: str, body: str) -> Dict[str, Any]:
        """Sends a plain text message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": True, "body": body},
        }
        return await self._send(payload)

    async def send_button_message(
        self,
        to: str,
        body: str,
        buttons: List[Dict[str, str]], # [{"id": "opt_1", "title": "Option 1"}]
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends an interactive quick-reply button message (max 3 buttons)."""
        interactive_buttons = []
        for btn in buttons[:3]:
            interactive_buttons.append({
                "type": "reply",
                "reply": {
                    "id": btn["id"],
                    "title": btn["title"][:20], # WhatsApp limit is 20 chars
                }
            })

        interactive: Dict[str, Any] = {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": interactive_buttons},
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._send(payload)

    async def send_list_message(
        self,
        to: str,
        body: str,
        button_text: str,
        sections: List[Dict[str, Any]],
        header: Optional[str] = None,
        footer: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Sends an interactive list message."""
        interactive: Dict[str, Any] = {
            "type": "list",
            "body": {"text": body},
            "action": {
                "button": button_text[:20],
                "sections": sections,
            }
        }
        if header:
            interactive["header"] = {"type": "text", "text": header}
        if footer:
            interactive["footer"] = {"text": footer}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "interactive",
            "interactive": interactive,
        }
        return await self._send(payload)

    async def send_image_message(self, to: str, image_url: str, caption: Optional[str] = None) -> Dict[str, Any]:
        """Sends an image message."""
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "image",
            "image": {"link": image_url, "caption": caption or ""},
        }
        return await self._send(payload)
