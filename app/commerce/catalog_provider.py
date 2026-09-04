import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CatalogItem
from app.models.order import Order
from app.commerce.payments.paystack import PaystackClient
from app.commerce.bumpa.client import BumpaClient
from app.core.config import settings
from app.core.logger import logger

# Words too common to be meaningful search signal on their own — dropped
# before matching so e.g. "shoes for the office" doesn't dilute ranking
# with hits on "the"/"for" across unrelated products.
_STOPWORDS = {"a", "an", "the", "for", "of", "in", "on", "with", "to", "and", "or", "is", "are", "me", "my", "i", "want", "need", "looking", "show", "find"}


class CatalogManager:
    """Unified multi-source catalog manager (Paystack, Bumpa, Local DB)."""

    @staticmethod
    def _query_words(query: str) -> List[str]:
        """Splits a free-text query into significant lowercase words, stripping
        punctuation and dropping stopwords/very-short tokens. E.g. "looking for
        a blue wireless earbud" -> ["blue", "wireless", "earbud"]."""
        raw_tokens = re.findall(r"[a-zA-Z0-9]+", query.lower())
        return [w for w in raw_tokens if len(w) >= 2 and w not in _STOPWORDS]

    @staticmethod
    async def search_products(
        db: AsyncSession,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[CatalogItem]:
        """Flexible multi-word matching: an item matching ANY significant word
        in the query is a candidate; results are ranked by how many distinct
        query words it matched (title/description/category), most first —
        so a query like "blue wireless earbuds" still finds "Wireless Blue
        Earbuds Pro" even though the words appear in a different order and
        the title has an extra word, which a single %substring% match would
        have missed entirely."""
        words = CatalogManager._query_words(query) if query else []

        stmt = select(CatalogItem)
        conditions = []

        if words:
            word_conditions = [
                or_(
                    CatalogItem.title.ilike(f"%{w}%"),
                    CatalogItem.description.ilike(f"%{w}%"),
                    CatalogItem.category.ilike(f"%{w}%"),
                )
                for w in words
            ]
            conditions.append(or_(*word_conditions))
        elif query:
            # Query had no significant words left after stopword removal
            # (e.g. just "the") — fall back to the raw substring so we don't
            # silently return everything.
            pattern = f"%{query.strip()}%"
            conditions.append(
                or_(
                    CatalogItem.title.ilike(pattern),
                    CatalogItem.description.ilike(pattern),
                    CatalogItem.category.ilike(pattern),
                )
            )

        if category:
            conditions.append(CatalogItem.category.ilike(f"%{category.strip()}%"))

        if conditions:
            stmt = stmt.where(*conditions)

        # Fetch a superset (uncapped by `limit` here) so ranking-by-word-count
        # can pick the truly best matches rather than an arbitrary DB-order
        # slice; small single-business catalogs make this cheap.
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

        if not words:
            return candidates[:limit]

        def _match_count(item: CatalogItem) -> int:
            haystack = " ".join(filter(None, [item.title, item.description, item.category])).lower()
            return sum(1 for w in words if w in haystack)

        candidates.sort(key=_match_count, reverse=True)
        return candidates[:limit]

    @staticmethod
    async def get_featured_products(
        db: AsyncSession,
        limit: int = 6,
        lookback_days: int = 60,
    ) -> List[CatalogItem]:
        """Ranks products for the undirected "browse" case (no search query):
        recent order frequency first, newest-listed as the tiebreak. Order
        popularity is computed in Python (fetch recent orders, tally a
        Counter over items_json) rather than a DB-side JSON aggregate, since
        this app supports both SQLite and Postgres and catalog/order volumes
        here are small (single-business scale) — no need for DB-specific
        JSON functions."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        order_stmt = select(Order).where(
            Order.status.in_(["paid", "processing", "completed"]),
            Order.created_at >= cutoff,
        )
        order_result = await db.execute(order_stmt)
        recent_orders = order_result.scalars().all()

        popularity: Counter = Counter()
        for order in recent_orders:
            try:
                items = json.loads(order.items_json or "[]")
            except Exception:
                continue
            for entry in items:
                # Cart-driven checkouts write "item_id" (see app/commerce/cart.py);
                # AI-tool-driven create_order writes "product_id" — check both.
                pid = entry.get("item_id")
                if pid is None:
                    pid = entry.get("product_id")
                if pid is not None:
                    popularity[pid] += 1

        item_stmt = select(CatalogItem)
        item_result = await db.execute(item_stmt)
        all_items = list(item_result.scalars().all())

        all_items.sort(
            key=lambda item: (
                popularity.get(item.id, 0),
                item.created_at or datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )
        return all_items[:limit]

    @staticmethod
    async def get_product_by_id(db: AsyncSession, product_id: int) -> Optional[CatalogItem]:
        stmt = select(CatalogItem).where(CatalogItem.id == product_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def sync_external_catalog(db: AsyncSession, source: Optional[str] = None) -> int:
        """Syncs catalog products from Paystack or Bumpa into local database."""
        target_source = (source or settings.CATALOG_SOURCE).lower()
        logger.info(f"Syncing catalog from external source: {target_source.upper()}")

        fetched_products: List[Dict[str, Any]] = []

        if target_source == "paystack":
            if settings.PAYSTACK_SECRET_KEY:
                fetched_products = await PaystackClient().fetch_products()
        elif target_source == "bumpa":
            if settings.BUMPA_API_KEY:
                fetched_products = await BumpaClient().fetch_products()
        elif target_source == "local":
            logger.info("Local catalog active; skipping external API sync.")
            return 0

        synced_count = 0
        for item in fetched_products:
            ext_id = item.get("external_id")
            stmt = select(CatalogItem).where(
                CatalogItem.external_id == ext_id,
                CatalogItem.source == item.get("source", target_source)
            )
            result = await db.execute(stmt)
            existing = result.scalars().first()

            if existing:
                existing.title = item["title"]
                existing.description = item.get("description")
                existing.price = item["price"]
                existing.currency = item.get("currency", "NGN")
                existing.in_stock = item.get("in_stock", True)
                existing.stock_quantity = item.get("stock_quantity", 100)
                existing.image_url = item.get("image_url")
            else:
                new_item = CatalogItem(
                    source=item.get("source", target_source),
                    external_id=ext_id,
                    title=item["title"],
                    description=item.get("description"),
                    price=item["price"],
                    currency=item.get("currency", "NGN"),
                    in_stock=item.get("in_stock", True),
                    stock_quantity=item.get("stock_quantity", 100),
                    image_url=item.get("image_url"),
                )
                db.add(new_item)
            synced_count += 1

        await db.commit()
        logger.info(f"Successfully synced {synced_count} products from {target_source.upper()}")
        return synced_count
