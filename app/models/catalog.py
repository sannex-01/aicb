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
    image_url = Column(String(500), nullable=True)
    in_stock = Column(Boolean, default=True)
    stock_quantity = Column(Integer, default=100)
    
    # Access Group Scoping: JSON array of group IDs e.g. [1, 2]. Empty [] = globally accessible to all agents.
    access_group_ids_json = Column(Text, default="[]")
    access_tags_json = Column(Text, default="[]")
    
    metadata_json = Column(Text, default="{}")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
