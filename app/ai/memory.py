import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.logger import logger
from app.models.session import ConversationSession, MessageLog


class MemoryManager:
    """Manages sliding window conversation context and TTL session expiry."""

    @staticmethod
    async def get_or_create_session(
        db: AsyncSession,
        channel: str,
        customer_identifier: str,
    ) -> ConversationSession:
        session_key = f"{channel}:{customer_identifier}"
        now = datetime.now(timezone.utc)

        stmt = select(ConversationSession).where(ConversationSession.session_key == session_key)
        result = await db.execute(stmt)
        session = result.scalars().first()

        if not session:
            session = ConversationSession(
                session_key=session_key,
                channel=channel,
                customer_identifier=customer_identifier,
                bot_mode=settings.BOT_MODE,
                memory_json="[]",
                state_data="{}",
                last_active_at=now,
                expires_at=now + timedelta(hours=settings.SESSION_EXPIRY_HOURS),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)
            return session

        # Check if session has expired
        if session.expires_at and session.expires_at < now:
            logger.info(f"Session {session_key} expired at {session.expires_at}. Resetting active context.")
            session.memory_json = "[]"
            session.active_flow = None
            session.current_step = None
            session.state_data = "{}"

        # Refresh expiry and active time
        session.last_active_at = now
        session.expires_at = now + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    def get_history(session: ConversationSession) -> List[Dict[str, Any]]:
        """Returns the list of serialized conversation turns."""
        try:
            return json.loads(session.memory_json or "[]")
        except Exception:
            return []

    @staticmethod
    async def add_message(
        db: AsyncSession,
        session: ConversationSession,
        role: str,
        content: str,
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Appends a message to message logs and updates sliding memory buffer."""
        # 1. Add permanent message log
        log_entry = MessageLog(
            session_id=session.id,
            role=role,
            content=content,
            tool_calls_json=json.dumps(tool_calls) if tool_calls else None,
            metadata_json=json.dumps(metadata or {}),
        )
        db.add(log_entry)

        # 2. Update sliding memory
        history = MemoryManager.get_history(session)
        msg_payload = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if tool_calls:
            msg_payload["tool_calls"] = tool_calls

        history.append(msg_payload)

        # Trim to sliding window size
        if len(history) > settings.MEMORY_WINDOW_SIZE * 2:
            history = history[-(settings.MEMORY_WINDOW_SIZE * 2):]

        session.memory_json = json.dumps(history)
        session.last_active_at = datetime.now(timezone.utc)
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
        await db.commit()

    @staticmethod
    async def update_flow_state(
        db: AsyncSession,
        session: ConversationSession,
        active_flow: Optional[str],
        current_step: Optional[str],
        state_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Updates interactive button flow progress."""
        session.active_flow = active_flow
        session.current_step = current_step
        if state_data is not None:
            session.state_data = json.dumps(state_data)
        session.last_active_at = datetime.now(timezone.utc)
        session.expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.SESSION_EXPIRY_HOURS)
        await db.commit()

    @staticmethod
    def get_flow_state_data(session: ConversationSession) -> Dict[str, Any]:
        """Returns the current state dictionary for the active flow."""
        try:
            return json.loads(session.state_data or "{}")
        except Exception:
            return {}

    @staticmethod
    async def reset_session(db: AsyncSession, session: ConversationSession) -> None:
        """Clears memory and active flow state manually."""
        session.memory_json = "[]"
        session.active_flow = None
        session.current_step = None
        session.state_data = "{}"
        await db.commit()
