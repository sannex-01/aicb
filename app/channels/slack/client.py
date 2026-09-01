from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.core.logger import logger


class SlackDispatcher:
    """Dispatches human escalation alerts to a Slack channel via incoming webhook."""

    @staticmethod
    async def dispatch_escalation(
        customer_identifier: str,
        channel: str,
        reason: str,
        urgency: str = "medium",
        context_preview: Optional[str] = None,
    ) -> bool:
        if not settings.SLACK_WEBHOOK_URL:
            logger.info("Slack Webhook URL not configured. Escalation logged internally.")
            return False

        urgency_emoji = {"low": "🟡", "medium": "🟠", "high": "🔴"}.get(urgency.lower(), "🟠")

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{urgency_emoji} Customer Escalation Required ({channel.upper()})",
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Customer:*\n`{customer_identifier}`"},
                    {"type": "mrkdwn", "text": f"*Channel:*\n{channel.capitalize()}"},
                    {"type": "mrkdwn", "text": f"*Urgency:*\n{urgency.upper()}"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n{reason}"},
                ]
            }
        ]

        if context_preview:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Recent Conversation Context:*\n```{context_preview[:500]}```"
                }
            })

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(settings.SLACK_WEBHOOK_URL, json={"blocks": blocks})
                return res.status_code == 200
        except Exception as e:
            logger.error(f"Failed to post escalation to Slack: {e}")
            return False
