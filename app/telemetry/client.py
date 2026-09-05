import queue
import threading
import time
from typing import Optional, Dict, Any, List
import httpx
from app.core.config import settings
from app.core.logger import logger


import os
from typing import Optional, Dict, Any
from sannex_agent import SannexClient
from app.core.config import settings

class TelemetryWrapper:
    def __init__(self):
        self.api_key = settings.SANNEX_API_KEY
        self.host = settings.SANNEX_HOST
        self._client = None
        
        if self.api_key and settings.ENABLE_TELEMETRY:
            self._client = SannexClient(api_key=self.api_key, host=self.host)

    def track(
        self,
        channel: str,
        customer_id: str,
        event: str,
        status: str = "success",
        amount: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> None:
        """Enqueues an event using the official SannexAgent SDK."""
        if not self._client or not settings.ENABLE_TELEMETRY:
            return

        # The Python SDK supports batching natively in track()
        self._client.track(
            channel=channel,
            customer_id=customer_id,
            event=event,
            status=status,
            amount=amount,
            metadata=metadata,
            agent_id=agent_id,
        )

    def sync_conversation(
        self,
        channel: str,
        customer_id: str,
        messages: List[Dict[str, Any]],
        agent_id: Optional[str] = None,
    ) -> None:
        """Push a batched conversation transcript up to AgentOS."""
        if not self._client or not settings.ENABLE_TELEMETRY:
            return
        
        # Will fail gracefully if the installed sannex_agent package is outdated
        if hasattr(self._client, "sync_conversation"):
            self._client.sync_conversation(
                channel=channel,
                customer_id=customer_id,
                messages=messages,
                agent_id=agent_id,
            )
        else:
            logger.warning("sannex_agent SDK is outdated, missing sync_conversation.")

    def close(self) -> None:
        if self._client:
            self._client.close()

telemetry_client = TelemetryWrapper()
