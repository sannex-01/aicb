from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.core.database import Base


class ConfigOverride(Base):
    """Dynamic configuration overrides fetched from AgentOS dashboard."""
    __tablename__ = "config_overrides"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    key = Column(String(100), unique=True, index=True, nullable=False) # e.g. 'system_prompt', 'temperature', 'model_name'
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
