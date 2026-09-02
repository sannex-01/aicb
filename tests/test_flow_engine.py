import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.catalog import CatalogItem
from app.ai.memory import MemoryManager
from app.flows.engine import FlowEngine

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
async def test_flow_engine_menu(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="whatsapp", customer_identifier="+2348000000000"
    )
    res = await FlowEngine.handle_action(test_db, session, action_id="menu")
    assert res["type"] == "buttons"
    assert len(res["buttons"]) == 3
    assert session.active_flow == "main_menu"


@pytest.mark.asyncio
async def test_flow_engine_browse_catalog(test_db: AsyncSession):
    product = CatalogItem(
        title="Wireless Headphones",
        description="Noise cancelling headphones",
        price=45000.0,
        currency="NGN",
    )
    test_db.add(product)
    await test_db.commit()

    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="12345"
    )
    res = await FlowEngine.handle_action(test_db, session, action_id="flow_browse_catalog")
    assert res["type"] in ["text", "buttons"]
    assert "Wireless Headphones" in res["text"]
    assert "45,000.00 NGN" in res["text"]
