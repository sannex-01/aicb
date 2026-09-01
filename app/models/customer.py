from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.core.database import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=True)
    phone_number = Column(String(50), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    
    # Channel Identifiers
    wa_id = Column(String(100), nullable=True, unique=True, index=True)
    telegram_id = Column(String(100), nullable=True, unique=True, index=True)
    
    metadata_json = Column(Text, nullable=True, default="{}")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
