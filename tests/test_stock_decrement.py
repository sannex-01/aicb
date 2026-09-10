import json

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base
from app.models.catalog import CatalogItem
from app.models.product_variant import ProductVariant
from app.models.order import Order
from app.commerce.catalog_provider import CatalogManager

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


async def _mk_order(db, items, ref="ORD-TEST-1"):
    order = Order(
        order_reference=ref,
        customer_identifier="+2348000000000",
        channel="whatsapp",
        status="paid",
        total_amount=1000.0,
        currency="NGN",
        items_json=json.dumps(items),
        metadata_json="{}",
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@pytest.mark.asyncio
async def test_tracked_product_stock_decrements(test_db: AsyncSession):
    p = CatalogItem(title="Mug", price=2500.0, currency="NGN", stock_quantity=10, in_stock=True, track_stock=True)
    test_db.add(p)
    await test_db.commit()
    await test_db.refresh(p)

    order = await _mk_order(test_db, [{"item_id": p.id, "title": "Mug", "quantity": 3}])
    await CatalogManager.decrement_stock_for_order(test_db, order)

    await test_db.refresh(p)
    assert p.stock_quantity == 7
    assert p.in_stock is True


@pytest.mark.asyncio
async def test_stock_clamps_at_zero_and_flips_in_stock(test_db: AsyncSession):
    p = CatalogItem(title="Poster", price=1000.0, currency="NGN", stock_quantity=2, in_stock=True, track_stock=True)
    test_db.add(p)
    await test_db.commit()
    await test_db.refresh(p)

    order = await _mk_order(test_db, [{"item_id": p.id, "title": "Poster", "quantity": 5}])
    await CatalogManager.decrement_stock_for_order(test_db, order)

    await test_db.refresh(p)
    assert p.stock_quantity == 0
    assert p.in_stock is False


@pytest.mark.asyncio
async def test_unlimited_stock_never_decrements(test_db: AsyncSession):
    p = CatalogItem(title="Consulting", price=50000.0, currency="NGN", stock_quantity=100, in_stock=True, track_stock=False)
    test_db.add(p)
    await test_db.commit()
    await test_db.refresh(p)

    order = await _mk_order(test_db, [{"item_id": p.id, "title": "Consulting", "quantity": 4}])
    await CatalogManager.decrement_stock_for_order(test_db, order)

    await test_db.refresh(p)
    assert p.stock_quantity == 100
    assert p.in_stock is True


@pytest.mark.asyncio
async def test_decrement_is_idempotent(test_db: AsyncSession):
    p = CatalogItem(title="Cap", price=3000.0, currency="NGN", stock_quantity=10, in_stock=True, track_stock=True)
    test_db.add(p)
    await test_db.commit()
    await test_db.refresh(p)

    order = await _mk_order(test_db, [{"item_id": p.id, "title": "Cap", "quantity": 2}])
    await CatalogManager.decrement_stock_for_order(test_db, order)
    await CatalogManager.decrement_stock_for_order(test_db, order)  # webhook redelivery

    await test_db.refresh(p)
    assert p.stock_quantity == 8


@pytest.mark.asyncio
async def test_variant_stock_decrements_not_parent(test_db: AsyncSession):
    p = CatalogItem(title="Tee", price=8000.0, currency="NGN", stock_quantity=50, in_stock=True, track_stock=True, has_variants=True)
    test_db.add(p)
    await test_db.commit()
    await test_db.refresh(p)
    v = ProductVariant(catalog_item_id=p.id, name="Large / Blue", stock_quantity=6, in_stock=True, track_stock=True)
    test_db.add(v)
    await test_db.commit()
    await test_db.refresh(v)

    order = await _mk_order(test_db, [{"item_id": p.id, "variant_id": v.id, "title": "Tee (Large / Blue)", "quantity": 2}])
    await CatalogManager.decrement_stock_for_order(test_db, order)

    await test_db.refresh(p)
    await test_db.refresh(v)
    assert v.stock_quantity == 4
    assert p.stock_quantity == 50  # parent untouched when a variant was purchased
