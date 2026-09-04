from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.core.config import settings


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_key = Column(String(150), unique=True, index=True, nullable=False) # e.g. "whatsapp:+23480..." or "telegram:123456"
    channel = Column(String(50), nullable=False) # whatsapp, telegram
    customer_identifier = Column(String(100), nullable=False, index=True)
    
    # Active state & interactive flow tracking
    bot_mode = Column(String(50), default="hybrid") # conversational, interactive_flow, hybrid
    active_flow = Column(String(100), nullable=True) # e.g. "order_flow", "support_flow"
    current_step = Column(String(100), nullable=True) # e.g. "select_product", "ask_address"
    state_data = Column(Text, default="{}") # JSON payload storing temporary collected data
    
    # Sliding window conversation memory (serialized JSON list of role/content)
    memory_json = Column(Text, default="[]")
    
    last_active_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    expires_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
    )
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    messages = relationship("MessageLog", back_populates="session", cascade="all, delete-orphan")


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("conversation_sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False) # user, assistant, system, tool
    content = Column(Text, nullable=False)
    tool_calls_json = Column(Text, nullable=True)
    metadata_json = Column(Text, default="{}")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("ConversationSession", back_populates="messages")
