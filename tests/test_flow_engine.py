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


@pytest.mark.asyncio
async def test_flow_engine_profile_empty_state(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="tg_user_1001"
    )
    res = await FlowEngine.handle_action(test_db, session, action_id="flow_my_profile")
    assert "Your Profile Details" in res.text
    assert "• *Full Name:* [Not Set]" in res.text
    assert "• *Email Address:* [Not Set]" in res.text
    assert "• *Phone Number:* [Not Set]" in res.text
    assert any(b.id == "flow_start_profile_edit" and "Create Profile" in b.title for b in res.buttons)
    assert any(b.id == "flow_main_menu" and "Main Menu" in b.title for b in res.buttons)


@pytest.mark.asyncio
async def test_flow_engine_profile_populated_state(test_db: AsyncSession):
    from app.commerce.customer_profile import upsert_customer

    await upsert_customer(
        test_db,
        channel="telegram",
        identifier="tg_user_2002",
        name="Ada Lovelace",
        email="ada@example.com",
        phone="+2348012345678",
    )

    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="tg_user_2002"
    )
    res = await FlowEngine.handle_action(test_db, session, action_id="flow_my_profile")
    assert "Your Profile Details" in res.text
    assert "Ada Lovelace" in res.text
    assert "ada@example.com" in res.text
    assert "+2348012345678" in res.text
    assert any(b.id == "flow_start_profile_edit" and "Update Profile" in b.title for b in res.buttons)
    assert any(b.id == "flow_main_menu" for b in res.buttons)


@pytest.mark.asyncio
async def test_flow_engine_profile_widget_omitted(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="widget", customer_identifier="widget_sess_123"
    )
    # 1. Widget main menu should not include profile button
    menu_res = await FlowEngine.handle_action(test_db, session, action_id="menu")
    assert not any(b.id == "flow_my_profile" for b in menu_res.buttons)

    # 2. Directly invoking profile action in widget falls back to main menu
    prof_res = await FlowEngine.handle_action(test_db, session, action_id="flow_my_profile")
    assert not any(b.id == "flow_my_profile" for b in prof_res.buttons)
    assert any(b.id == "flow_browse_catalog" for b in prof_res.buttons)


@pytest.mark.asyncio
async def test_flow_engine_profile_create_flow(test_db: AsyncSession):
    session = await MemoryManager.get_or_create_session(
        test_db, channel="telegram", customer_identifier="tg_user_3003"
    )

    # 1. Trigger profile create
    r1 = await FlowEngine.handle_action(test_db, session, action_id="flow_start_profile_edit")
    assert "What's your full name?" in r1.text
    assert session.active_flow == "profile_collect"
    assert session.current_step == "ask_name"

    # 2. Provide name
    r2 = await FlowEngine.handle_action(test_db, session, action_id="John Doe", user_input="John Doe")
    assert "What's your email address?" in r2.text
    assert session.current_step == "ask_email"

    # 3. Provide email
    r3 = await FlowEngine.handle_action(test_db, session, action_id="john@example.com", user_input="john@example.com")
    assert "What's your phone number?" in r3.text
    assert session.current_step == "ask_phone"

    # 4. Provide phone
    r4 = await FlowEngine.handle_action(test_db, session, action_id="+2348011223344", user_input="+2348011223344")
    assert "Profile saved successfully!" in r4.text
    assert "John Doe" in r4.text
    assert "john@example.com" in r4.text
    assert "+2348011223344" in r4.text
    assert any(b.id == "flow_start_profile_edit" and "Update Profile" in b.title for b in r4.buttons)

    # 5. Check profile view again
    r5 = await FlowEngine.handle_action(test_db, session, action_id="flow_my_profile")
    assert "John Doe" in r5.text
    assert "john@example.com" in r5.text
    assert any(b.id == "flow_start_profile_edit" and "Update Profile" in b.title for b in r5.buttons)

