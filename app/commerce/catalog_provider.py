from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.catalog import CatalogItem
from app.commerce.payments.paystack import PaystackClient
from app.commerce.bumpa.client import BumpaClient
from app.core.config import settings
from app.core.logger import logger


class CatalogManager:
    """Unified multi-source catalog manager (Paystack, Bumpa, Local DB)."""

    @staticmethod
    async def search_products(
        db: AsyncSession,
        query: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 10,
    ) -> List[CatalogItem]:
        stmt = select(CatalogItem)
        conditions = []

        if query:
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

        stmt = stmt.limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

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
