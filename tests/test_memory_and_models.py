import pytest
import pytest_asyncio
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.customer import Customer
from app.models.catalog import CatalogItem
from app.models.session import ConversationSession
from app.ai.memory import MemoryManager

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

@pytest_asyncio.fixture
async def test_db():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_memory_session_lifecycle(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="whatsapp", customer_identifier="+2348012345678"
    )
    assert session.session_key == "whatsapp:+2348012345678"
    assert session.channel == "whatsapp"

    # Add messages
    await MemoryManager.add_message(test_db, session, role="user", content="Hello!")
    await MemoryManager.add_message(test_db, session, role="assistant", content="Hi, how can I help you?")

    history = MemoryManager.get_history(session)
    assert len(history) == 2
    assert history[0]["content"] == "Hello!"
    assert history[1]["content"] == "Hi, how can I help you?"


@pytest.mark.asyncio
async def test_session_ttl_expiry(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="987654"
    )
    await MemoryManager.add_message(test_db, session, role="user", content="Old inquiry")

    # Manually expire the session
    session.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await test_db.commit()

    # Re-fetching session should automatically clear expired memory
    refreshed_session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="987654"
    )
    history = MemoryManager.get_history(refreshed_session)
    assert len(history) == 0
