import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.knowledge import KnowledgeDoc
from app.ai.rag import RAGEngine

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
async def test_rag_retrieval(test_db: AsyncSession):
    doc1 = KnowledgeDoc(
        title="Return Policy",
        category="Policies",
        content="Items can be returned within 14 days of purchase in original packaging.",
        tags="returns refund warranty",
    )
    doc2 = KnowledgeDoc(
        title="Shipping Details",
        category="Shipping",
        content="Standard delivery takes 2 to 4 business days across Lagos and Abuja.",
        tags="shipping delivery timeline",
    )
    test_db.add_all([doc1, doc2])
    await test_db.commit()

    context = await RAGEngine.retrieve_relevant_context(test_db, query="How do I return an item?", top_k=1)
    assert "Return Policy" in context
    assert "14 days" in context
