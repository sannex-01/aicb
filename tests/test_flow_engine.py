import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.core.database import Base
from app.models.catalog import CatalogItem
from app.ai.memory import MemoryManager
from app.commerce.cart import CartManager
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
    assert res.text is not None
    assert len(res.buttons) >= 3
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
    assert "Wireless Headphones" in res.text
    assert "45,000.00 NGN" in res.text
    assert len(res.product_cards) >= 1
    assert any(b.id == f"cart_add_{product.id}" for b in res.buttons)


@pytest.mark.asyncio
async def test_product_click_and_quantity_selection(test_db: AsyncSession):
    product = CatalogItem(
        title="Velvet Silk Evening Gown",
        description="Elegant evening gown",
        price=500.0,
        currency="NGN",
    )
    test_db.add(product)
    await test_db.commit()

    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="cust_999"
    )

    # 1. Click on product -> adds 1 to cart and returns quantity selection buttons
    res1 = await FlowEngine.handle_action(test_db, session, action_id=f"cart_add_{product.id}")
    assert "Added 1x Velvet Silk Evening Gown" in res1.text
    assert session.active_flow == "quantity_select"
    assert any(b.id == f"qty_set_{product.id}_2" for b in res1.buttons)
    assert any(b.id == "flow_view_cart" for b in res1.buttons)
    assert any(b.id == "flow_browse_catalog" for b in res1.buttons)

    cart1 = CartManager.get_cart(session)
    assert len(cart1) == 1
    assert cart1[0]["quantity"] == 1

    # 2. Click preset quantity button (e.g. Qty: 3)
    res2 = await FlowEngine.handle_action(test_db, session, action_id=f"qty_set_{product.id}_3")
    assert "3x Velvet Silk Evening Gown" in res2.text
    cart2 = CartManager.get_cart(session)
    assert cart2[0]["quantity"] == 3

    # 3. Send custom number in chat (e.g. "5")
    res3 = await FlowEngine.handle_action(test_db, session, action_id="5", user_input="5")
    assert "5x Velvet Silk Evening Gown" in res3.text
    cart3 = CartManager.get_cart(session)
    assert cart3[0]["quantity"] == 5

    # 4. View Cart
    res_cart = await FlowEngine.handle_action(test_db, session, action_id="flow_view_cart")
    assert "Your Shopping Cart" in res_cart.text
    assert "2,500.00 NGN" in res_cart.text
    assert any(b.id == "flow_browse_catalog" for b in res_cart.buttons)
    assert any(b.id == "flow_checkout" for b in res_cart.buttons)
