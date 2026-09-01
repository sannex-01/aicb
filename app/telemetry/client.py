import queue
import threading
import time
from typing import Optional, Dict, Any, List
import httpx
from app.core.config import settings
from app.core.logger import logger


class AICBTelemetryClient:
    """Ultra-lightweight background telemetry dispatcher for Sannex Agent."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        flush_interval: float = 2.0,
        max_queue_size: int = 1000,
    ):
        self.api_key = api_key or settings.SANNEX_API_KEY
        self.host = (host or settings.SANNEX_HOST).rstrip("/")
        self.endpoint = f"{self.host}/v1/events"
        self.flush_interval = flush_interval
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._running = True
        self._client = httpx.Client(timeout=4.0)

        # Start daemon background thread
        if self.api_key and settings.ENABLE_TELEMETRY:
            self._worker_thread = threading.Thread(target=self._worker, daemon=True)
            self._worker_thread.start()

    def track(
        self,
        channel: str,
        customer_id: str,
        event: str,
        status: str = "success",
        amount: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Enqueues an event to be dispatched asynchronously without blocking the caller."""
        if not self.api_key or not settings.ENABLE_TELEMETRY:
            return

        payload = {
            "channel": channel,
            "customer_id": str(customer_id),
            "event": event,
            "status": status,
            "amount": float(amount),
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            pass  # Safely drop to avoid degrading host performance

    def _worker(self) -> None:
        while self._running:
            events: List[Dict[str, Any]] = []
            while not self._queue.empty() and len(events) < 50:
                try:
                    events.append(self._queue.get_nowait())
                except queue.Empty:
                    break

            if events:
                self._flush(events)
            time.sleep(self.flush_interval)

    def _flush(self, events: List[Dict[str, Any]]) -> None:
        try:
            self._client.post(
                self.endpoint,
                json={"batch": events},
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
        except Exception as e:
            # Never raise or break host performance
            logger.debug(f"Telemetry flush swallowed exception: {e}")

    def close(self) -> None:
        self._running = False
        try:
            self._client.close()
        except Exception:
            pass


telemetry_client = AICBTelemetryClient()
