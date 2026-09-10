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


@pytest.mark.asyncio
async def test_rag_retrieval_scoped_by_access_group(test_db: AsyncSession):
    # Doc scoped to access group 5 — the group id is mirrored into
    # access_tags_json exactly as the knowledge API writes it.
    scoped = KnowledgeDoc(
        title="VIP Concierge Playbook",
        category="Internal",
        content="Offer VIP customers free next-day delivery and a dedicated line.",
        access_group_ids_json="[5]",
        access_tags_json='["5"]',
    )
    public = KnowledgeDoc(
        title="Store Hours",
        category="General",
        content="We are open Monday to Saturday, 9am to 6pm.",
        access_group_ids_json="[]",
        access_tags_json="[]",
    )
    test_db.add_all([scoped, public])
    await test_db.commit()

    # An agent in group 5 sees both.
    ctx_in = await RAGEngine.retrieve_relevant_context(
        test_db, query="VIP delivery perks", top_k=5, allowed_access_tags={"5"}
    )
    assert "VIP Concierge Playbook" in ctx_in

    # An agent in a different group only sees the public doc.
    ctx_out = await RAGEngine.retrieve_relevant_context(
        test_db, query="VIP delivery perks", top_k=5, allowed_access_tags={"9"}
    )
    assert "VIP Concierge Playbook" not in ctx_out
