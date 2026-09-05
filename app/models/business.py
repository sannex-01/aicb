from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from app.core.database import Base


class BusinessProfile(Base):
    __tablename__ = "business_profile"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False, default="My Business")
    currency = Column(String(10), nullable=False, default="NGN")
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    address = Column(Text, nullable=True)
    logo_url = Column(String(500), nullable=True)
    
    # Standalone Platform API Key (stored as SHA-256 hash)
    api_key_hash = Column(String(255), nullable=True)
    api_key_prefix = Column(String(50), nullable=True)
    api_key_created_at = Column(DateTime(timezone=True), nullable=True)
    
    is_configured = Column(Boolean, default=False)
    metadata_json = Column(Text, default="{}")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
