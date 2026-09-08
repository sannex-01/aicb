from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from app.core.database import Base


class ProductVariant(Base):
    """A purchasable option of a CatalogItem, e.g. "Large / Blue" for a
    T-shirt. A product with zero rows here is sold as-is, exactly like
    today — variants are opt-in, not a required concept for every product.
    See CatalogItem.has_variants, kept in sync as a cheap existence flag."""
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    catalog_item_id = Column(Integer, ForeignKey("catalog_items.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)  # e.g. "Large / Blue"
    sku = Column(String(100), nullable=True, index=True)

    # Null = falls back to the parent CatalogItem's price. Many variants
    # (e.g. just a color choice) are the same price as the base product,
    # so this avoids forcing every variant row to duplicate the price.
    price_override = Column(Float, nullable=True)

    stock_quantity = Column(Integer, default=100)
    in_stock = Column(Boolean, default=True)

    # Structured attributes for future filtering/display, e.g. {"size": "L", "color": "Blue"}.
    # Not required — `name` alone is enough for the chat flow to show/store
    # a variant today; this is groundwork, not load-bearing yet.
    attributes_json = Column(Text, default="{}")
    metadata_json = Column(Text, default="{}")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
