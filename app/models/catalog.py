from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text
from app.core.database import Base


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    source = Column(String(50), default="local", index=True) # local, paystack, bumpa
    external_id = Column(String(100), nullable=True, index=True) # ID on Paystack or Bumpa
    title = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="NGN")
    category = Column(String(100), nullable=True, index=True)
    subcategory = Column(String(100), nullable=True, index=True)
    image_url = Column(String(500), nullable=True)
    in_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=100)

    # When False, this item has no inventory limit: it's always purchasable
    # regardless of stock_quantity, and stock is never decremented on
    # purchase. The natural default for service/digital items (which have
    # nothing to count) — the product form auto-unsets it when
    # fulfillment_type is "service" or "digital", but a business can still
    # override either way. When True (physical goods default), each paid
    # order reduces stock_quantity and flips in_stock off at zero.
    track_stock = Column(Boolean, default=True)

    # True when this item has one or more rows in product_variants (see
    # app/models/product_variant.py). A cheap flag so callers (the chat
    # flow's cart_add_ handler, the dashboard's product list) can check
    # "does this need a variant-selection step?" without a join/count
    # query on every product in a list. Kept in sync whenever variants
    # are added/removed for this item.
    has_variants = Column(Boolean, default=False)

    # True (default) for physical goods that need a delivery address before
    # checkout — the flow engine only triggers address collection when the
    # cart contains at least one such item. A business flips this off per
    # product for digital/service items in the product form.
    requires_shipping = Column(Boolean, default=True)

    # How this item is actually fulfilled after payment: "physical" (ships,
    # dispatched via FulfillmentManager's courier/Bumpa path — the
    # historical default, matches requires_shipping=True), "digital"
    # (delivered instantly via digital_asset_url, no shipping), "service"
    # (no automated dispatch at all — just a merchant notification).
    # Deliberately a separate concept from requires_shipping (which only
    # gates the ADDRESS COLLECTION step) rather than derived from it, since
    # a business could conceivably want delivery tracking without needing
    # an upfront address (e.g. pickup) — kept simple for now: physical
    # items default requires_shipping=True, digital/service default False,
    # but a business can still mix them if they have a real reason to.
    fulfillment_type = Column(String(20), default="physical")

    # The downloadable asset/link a digital product delivers on payment —
    # only meaningful when fulfillment_type == "digital". Anything
    # StorageManager can produce a URL for (an uploaded file, or a plain
    # external link the business already hosts elsewhere).
    digital_asset_url = Column(String(500), nullable=True)

    # Access Group Scoping: JSON array of group IDs e.g. [1, 2]. Empty [] = globally accessible to all agents.
    access_group_ids_json = Column(Text, default="[]")
    access_tags_json = Column(Text, default="[]")
    
    metadata_json = Column(Text, default="{}")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
