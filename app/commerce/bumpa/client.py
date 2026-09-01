from typing import Dict, Any, Optional, List
import httpx
from app.core.config import settings
from app.core.logger import logger


class BumpaClient:
    """Bumpa E-Commerce API client."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key or settings.BUMPA_API_KEY
        self.base_url = (base_url or settings.BUMPA_API_BASE_URL).rstrip("/")

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise ValueError("BUMPA_API_KEY is not configured.")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def fetch_products(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetches products from Bumpa API."""
        url = f"{self.base_url}/products?limit={limit}"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, headers=self._headers())
                data = res.json()
                if res.status_code == 200:
                    products = []
                    items = data.get("data", []) if isinstance(data.get("data"), list) else data.get("products", [])
                    for p in items:
                        products.append({
                            "external_id": str(p.get("id")),
                            "title": p.get("name") or p.get("title"),
                            "description": p.get("description", ""),
                            "price": float(p.get("price", 0.0)),
                            "currency": p.get("currency", "NGN"),
                            "in_stock": p.get("quantity", 1) > 0,
                            "stock_quantity": int(p.get("quantity", 100)),
                            "image_url": p.get("images", [{}])[0].get("url") if p.get("images") else None,
                            "source": "bumpa",
                        })
                    return products
                else:
                    logger.error(f"Bumpa products fetch failed: {res.text}")
                    return []
        except Exception as e:
            logger.error(f"Bumpa client error: {e}")
            return []

    async def create_order(self, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates an order in Bumpa store."""
        url = f"{self.base_url}/orders"
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=order_data, headers=self._headers())
            return res.json()
