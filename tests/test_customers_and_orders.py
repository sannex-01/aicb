import json

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from app.main import app
from app.models.customer import Customer
from app.models.order import Order, PaymentLog

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _auth(client):
    res = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Admin",
        "admin_email": "admin@example.com",
        "admin_password": "SuperSecretPassword123!",
        "business_name": "Test Biz",
    })
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.mark.asyncio
async def test_customer_order_stats_are_computed_live(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth(client)

    cust = Customer(name="Ada Lovelace", telegram_id="ada_tg", phone_number="+2348011112222", total_orders=0, total_spent=0.0)
    db_session.add(cust)
    await db_session.flush()

    # Two paid + one pending order, matched by the telegram identifier.
    db_session.add_all([
        Order(order_reference="ORD-1", customer_identifier="ada_tg", channel="telegram",
              items_json='[{"item_id":1,"quantity":1}]', total_amount=5000.0, currency="NGN", status="paid"),
        Order(order_reference="ORD-2", customer_identifier="ada_tg", channel="telegram",
              items_json='[{"item_id":2,"quantity":2}]', total_amount=8000.0, currency="NGN", status="completed"),
        Order(order_reference="ORD-3", customer_identifier="ada_tg", channel="telegram",
              items_json="[]", total_amount=3000.0, currency="NGN", status="pending"),
        # A different customer's order must not be counted.
        Order(order_reference="ORD-X", customer_identifier="someone_else", channel="telegram",
              items_json="[]", total_amount=99999.0, currency="NGN", status="paid"),
    ])
    await db_session.commit()

    # customers.total_orders / total_spent columns are still 0 in the DB,
    # but the API reports the live values.
    lst = await client.get("/api/v1/customers", headers=headers)
    row = next(c for c in lst.json()["items"] if c["name"] == "Ada Lovelace")
    assert row["total_orders"] == 3
    assert row["total_spent"] == 13000.0  # only paid + completed

    detail = await client.get(f"/api/v1/customers/{cust.id}", headers=headers)
    body = detail.json()
    assert body["customer"]["total_orders"] == 3
    assert body["customer"]["total_spent"] == 13000.0
    assert len(body["orders"]) == 3
    # No message transcripts in the customer payload anymore.
    assert "sessions" not in body
    assert "conversation_summary" in body


@pytest.mark.asyncio
async def test_order_detail_endpoint(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth(client)

    cust = Customer(name="Grace Hopper", phone_number="+2348090001111", email="grace@navy.mil")
    db_session.add(cust)

    order = Order(
        order_reference="ORD-DET-1",
        customer_identifier="+2348090001111",
        customer_name="Grace Hopper",
        customer_phone="+2348090001111",
        customer_email="grace@navy.mil",
        channel="whatsapp",
        items_json=json.dumps([
            {"item_id": 10, "title": "Compiler License", "quantity": 1, "price": 20000, "fulfillment_type": "digital"},
            {"item_id": 11, "title": "USB Cable", "quantity": 3, "price": 1500, "fulfillment_type": "physical"},
        ]),
        total_amount=24500.0,
        currency="NGN",
        status="paid",
        fulfillment_status="delivered_digital",
        payment_gateway="paystack",
        payment_reference="PS-REF-1",
        metadata_json=json.dumps({"fulfillment_groups": {"digital": {"status": "delivered_digital", "detail": "1 item delivered."}}}),
    )
    db_session.add(order)
    await db_session.flush()
    db_session.add(PaymentLog(order_reference="ORD-DET-1", gateway="paystack", gateway_reference="PS-REF-1",
                              amount=24500.0, currency="NGN", status="success"))
    await db_session.commit()

    res = await client.get(f"/api/v1/orders/{order.id}", headers=headers)
    assert res.status_code == 200
    body = res.json()

    assert body["order"]["order_reference"] == "ORD-DET-1"
    assert len(body["line_items"]) == 2
    assert body["line_items"][1]["line_total"] == 4500.0
    assert body["customer"]["name"] == "Grace Hopper"
    assert body["fulfillment"]["status"] == "delivered_digital"
    assert body["fulfillment"]["groups"]["digital"]["status"] == "delivered_digital"
    assert len(body["payments"]) == 1
    assert body["payments"][0]["status"] == "success"


@pytest.mark.asyncio
async def test_orders_list_scoped_to_customer(client: AsyncClient, db_session: AsyncSession):
    headers = await _auth(client)
    cust = Customer(name="Katherine Johnson", telegram_id="kj_tg")
    db_session.add(cust)
    await db_session.flush()
    db_session.add_all([
        Order(order_reference="ORD-KJ-1", customer_identifier="kj_tg", channel="telegram",
              items_json="[]", total_amount=1000.0, currency="NGN", status="paid"),
        Order(order_reference="ORD-OTHER", customer_identifier="nope", channel="telegram",
              items_json="[]", total_amount=1.0, currency="NGN", status="paid"),
    ])
    await db_session.commit()

    res = await client.get(f"/api/v1/orders?customer_id={cust.id}", headers=headers)
    refs = [o["order_reference"] for o in res.json()]
    assert refs == ["ORD-KJ-1"]
