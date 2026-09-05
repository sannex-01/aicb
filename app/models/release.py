from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from app.core.database import Base


class ReleaseNote(Base):
    __tablename__ = "release_notes"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    version = Column(String(50), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    changelog_json = Column(Text, default="[]")  # Serialized JSON list of strings
    release_date = Column(String(50), nullable=True)
    is_critical = Column(Boolean, default=False)
    download_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
