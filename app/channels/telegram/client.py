from typing import List, Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import logger


class TelegramClient:
    """Telegram Bot API Client."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.TELEGRAM_BOT_TOKEN

    async def _post(self, method: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.token:
            logger.info(f"[DEV MOCK] Telegram API {method} payload: {payload}")
            return {"ok": True, "result": {"message_id": 9999, "status": "mocked"}}

        url = f"https://api.telegram.org/bot{self.token}/{method}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload)
            data = res.json()
            if not data.get("ok"):
                logger.error(f"Telegram API {method} error: {data}")
            return data

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sends a text message with optional inline keyboard or custom keyboard, with fallback to plain text."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup
            
        res = await self._post("sendMessage", payload)
        if not res.get("ok") and parse_mode:
            # Fallback retry without Markdown formatting in case of unescaped characters
            logger.info("Retrying sendMessage without parse_mode markdown formatting...")
            payload.pop("parse_mode", None)
            res = await self._post("sendMessage", payload)
        return res

    async def send_inline_buttons(
        self,
        chat_id: int | str,
        text: str,
        buttons: List[List[Dict[str, str]]], # [[{"text": "Btn 1", "callback_data": "btn_1"}]]
    ) -> Dict[str, Any]:
        """Sends inline button grid."""
        markup = {"inline_keyboard": buttons}
        return await self.send_message(chat_id, text, reply_markup=markup)

    async def edit_message_text(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Edits an existing message text in-place on Telegram."""
        payload: Dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
        }
        if parse_mode:
            payload["parse_mode"] = parse_mode
        if reply_markup:
            payload["reply_markup"] = reply_markup

        res = await self._post("editMessageText", payload)
        if not res.get("ok"):
            desc = res.get("description", "").lower()
            if "message is not modified" in desc:
                return {"ok": True, "not_modified": True}
            if parse_mode:
                # Retry without Markdown formatting in case of unescaped special chars
                payload.pop("parse_mode", None)
                res = await self._post("editMessageText", payload)
                if not res.get("ok") and "message is not modified" in res.get("description", "").lower():
                    return {"ok": True, "not_modified": True}
        return res

    async def edit_inline_buttons(
        self,
        chat_id: int | str,
        message_id: int,
        text: str,
        buttons: Optional[List[List[Dict[str, str]]]] = None,
    ) -> Dict[str, Any]:
        """Edits an existing message's text and its inline keyboard in-place."""
        markup = {"inline_keyboard": buttons} if buttons is not None else None
        return await self.edit_message_text(chat_id, message_id, text, reply_markup=markup)

    async def send_webapp_button(
        self,
        chat_id: int | str,
        text: str,
        button_text: str,
        webapp_url: str,
    ) -> Dict[str, Any]:
        """Sends an inline button opening a Telegram MiniApp or Payment Webview."""
        markup = {
            "inline_keyboard": [
                [{"text": button_text, "web_app": {"url": webapp_url}}]
            ]
        }
        return await self.send_message(chat_id, text, reply_markup=markup)

    async def send_invoice(
        self,
        chat_id: int | str,
        title: str,
        description: str,
        payload: str,
        provider_token: str,
        currency: str,
        prices: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Sends a native Telegram payment invoice."""
        body = {
            "chat_id": chat_id,
            "title": title,
            "description": description,
            "payload": payload,
            "provider_token": provider_token or settings.TELEGRAM_PAYMENT_PROVIDER_TOKEN,
            "currency": currency.upper(),
            "prices": prices,
        }
        return await self._post("sendInvoice", body)

    async def answer_callback_query(self, callback_query_id: str, text: Optional[str] = None) -> Dict[str, Any]:
        """Acknowledges button clicks on Telegram."""
        payload: Dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        return await self._post("answerCallbackQuery", payload)

    async def answer_pre_checkout_query(self, pre_checkout_query_id: str, ok: bool = True, error_message: Optional[str] = None) -> Dict[str, Any]:
        """Confirms pre-checkout validity before Telegram executes payment."""
        payload: Dict[str, Any] = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": ok,
        }
        if not ok and error_message:
            payload["error_message"] = error_message
        return await self._post("answerPreCheckoutQuery", payload)

    async def set_chat_menu_button(self, webapp_url: str, text: str = "Store") -> Dict[str, Any]:
        """Configures Telegram Bot menu button to open Mini App webapp."""
        payload = {
            "menu_button": {
                "type": "web_app",
                "text": text,
                "web_app": {"url": webapp_url},
            }
        }
        return await self._post("setChatMenuButton", payload)
