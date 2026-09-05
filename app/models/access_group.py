from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Text
from app.core.database import Base


class AccessGroup(Base):
    __tablename__ = "access_groups"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    tags_json = Column(Text, default="[]")  # JSON serialized list of access tag strings for backward compatibility
    
    # LLM Provider Configuration for Access Group
    llm_provider = Column(String(50), nullable=True)  # openai, gemini, anthropic, groq, etc.
    api_key = Column(String(255), nullable=True)
    model_name = Column(String(100), nullable=True)
    
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
