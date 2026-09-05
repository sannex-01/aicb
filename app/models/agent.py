from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    
    # Brain & LLM configuration
    system_prompt = Column(Text, nullable=False)
    llm_provider = Column(String(50), default="gemini")  # gemini, openai, anthropic
    model_name = Column(String(100), default="gemini-2.5-flash")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1024)
    api_key_override = Column(String(255), nullable=True)
    
    # Mode & Behavior
    bot_mode = Column(String(50), default="conversational")  # conversational, interactive_flow, hybrid
    
    # Channel credentials
    whatsapp_phone_number_id = Column(String(100), nullable=True, index=True)
    whatsapp_access_token = Column(String(255), nullable=True)
    telegram_bot_token = Column(String(255), nullable=True, index=True)
    telegram_username = Column(String(100), nullable=True)
    widget_enabled = Column(Boolean, default=True)
    widget_profile_collection = Column(String(50), default="upfront")  # upfront, checkout
    
    # Access Scoping & Grouping (supports multiple access groups)
    group_id = Column(Integer, ForeignKey("access_groups.id", ondelete="SET NULL"), nullable=True)
    group_ids_json = Column(Text, default="[]")  # JSON array of group IDs e.g. [1, 2]
    access_tags_json = Column(Text, default="[]")  # JSON array of direct tags e.g. ["sales", "support"]
    
    is_active = Column(Boolean, default=True)
    is_default = Column(Boolean, default=False)
    
    total_messages = Column(Integer, default=0)
    total_orders = Column(Integer, default=0)
    total_revenue = Column(Float, default=0.0)
    last_active_at = Column(DateTime(timezone=True), nullable=True)
    
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    group = relationship("AccessGroup", lazy="joined")

    @property
    def whatsapp_phone_id(self) -> Optional[str]:
        return self.whatsapp_phone_number_id

    @whatsapp_phone_id.setter
    def whatsapp_phone_id(self, value: Optional[str]):
        self.whatsapp_phone_number_id = value

    @property
    def whatsapp_token(self) -> Optional[str]:
        return self.whatsapp_access_token

    @whatsapp_token.setter
    def whatsapp_token(self, value: Optional[str]):
        self.whatsapp_access_token = value

