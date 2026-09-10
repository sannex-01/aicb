import json

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from app.models.agent import Agent
from app.models.access_group import AccessGroup
from app.models.catalog import CatalogItem
from app.main import app

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_session: AsyncSession):
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


async def _seed_two_agents(db: AsyncSession):
    g1 = AccessGroup(name="Store One", tags_json='["store-one"]')
    g2 = AccessGroup(name="Store Two", tags_json='["store-two"]')
    db.add_all([g1, g2])
    await db.flush()

    a1 = Agent(name="Agent One", slug="agent-one", system_prompt="one", is_active=True,
               telegram_bot_token="111:AAA", group_id=g1.id)
    a2 = Agent(name="Agent Two", slug="agent-two", system_prompt="two", is_active=True,
               telegram_bot_token="222:BBB", group_id=g2.id)
    db.add_all([a1, a2])
    await db.flush()

    # One product per store, scoped to that store's access group id + tag.
    db.add(CatalogItem(title="One Widget", price=1000.0, currency="NGN", in_stock=True,
                       access_tags_json=json.dumps([str(g1.id), "store-one"])))
    db.add(CatalogItem(title="Two Gadget", price=2000.0, currency="NGN", in_stock=True,
                       access_tags_json=json.dumps([str(g2.id), "store-two"])))
    # A globally-scoped product (no groups, no tags) — must show for every agent.
    db.add(CatalogItem(title="Shared Sticker", price=100.0, currency="NGN", in_stock=True,
                       access_group_ids_json="[]", access_tags_json="[]"))
    await db.commit()
    return a1, a2


def _inline_query_update(agent_hint: str):
    return {
        "update_id": 1,
        "inline_query": {
            "id": f"iq-{agent_hint}",
            "from": {"id": 42, "username": "shopper"},
            "query": "",
            "chat_type": "sender",
        },
    }


@pytest.mark.asyncio
async def test_inline_search_scoped_to_agent_in_url(client: AsyncClient, test_session, monkeypatch):
    a1, a2 = await _seed_two_agents(test_session)

    captured = {}

    async def fake_answer_inline_query(self, inline_query_id, results, cache_time=30):
        captured[inline_query_id] = [r["title"] for r in results]
        return {"ok": True}

    async def fake_get_me(self):
        return {"ok": True, "result": {"username": "some_bot"}}

    monkeypatch.setattr("app.channels.telegram.client.TelegramClient.answer_inline_query", fake_answer_inline_query)
    monkeypatch.setattr("app.channels.telegram.client.TelegramClient.get_me", fake_get_me)

    r1 = await client.post(f"/api/v1/webhooks/telegram/{a1.id}", json=_inline_query_update("a1"))
    assert r1.status_code == 200
    r2 = await client.post(f"/api/v1/webhooks/telegram/{a2.id}", json=_inline_query_update("a2"))
    assert r2.status_code == 200

    titles_a1 = " ".join(captured["iq-a1"])
    titles_a2 = " ".join(captured["iq-a2"])
    assert "One Widget" in titles_a1 and "Two Gadget" not in titles_a1
    assert "Two Gadget" in titles_a2 and "One Widget" not in titles_a2
    # The globally-scoped product is visible to BOTH agents.
    assert "Shared Sticker" in titles_a1 and "Shared Sticker" in titles_a2


@pytest.mark.asyncio
async def test_ambiguous_webhook_without_agent_id_is_dropped(client: AsyncClient, test_session):
    await _seed_two_agents(test_session)

    # No /{agent_id} in the path and two token-bearing agents -> cannot route,
    # so the update is dropped rather than answered by the wrong agent.
    r = await client.post("/api/v1/webhooks/telegram", json={
        "update_id": 2,
        "message": {"chat": {"id": 99}, "from": {"id": 99, "first_name": "X"}, "text": "hello"},
    })
    assert r.status_code == 200
    assert r.json() == {"ok": True}
