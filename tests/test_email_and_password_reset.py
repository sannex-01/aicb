import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.core.database import Base, get_db
from app.main import app
from app.core.security import create_password_reset_jwt, decode_password_reset_jwt, verify_password
from app.services.email import EmailService
from app.models.user import AdminUser
from app.models.business import BusinessProfile

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
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


@pytest.mark.asyncio
async def test_password_reset_jwt_lifecycle():
    token = create_password_reset_jwt(user_id=42, email="admin@example.com", expires_minutes=15)
    assert token is not None

    decoded = decode_password_reset_jwt(token)
    assert decoded is not None
    assert decoded["sub"] == "42"
    assert decoded["email"] == "admin@example.com"
    assert decoded["purpose"] == "password_reset"

    # Invalid token returns None
    assert decode_password_reset_jwt("invalid.token.here") is None


@pytest.mark.asyncio
async def test_email_service_configuration(db_session: AsyncSession):
    # Initially not configured
    cfg = await EmailService.get_config(db_session)
    assert cfg["configured"] is False
    assert cfg["provider"] is None

    # Save Resend config
    saved = await EmailService.save_config(db_session, "resend", {
        "api_key": "re_test_1234567890abcdef",
        "from_email": "noreply@business.com",
        "from_name": "Acme Notifications",
    })
    assert saved["configured"] is True
    assert saved["provider"] == "resend"
    assert saved["config"]["from_email"] == "noreply@business.com"
    assert "..." in saved["config"]["api_key_masked"]


@pytest.mark.asyncio
async def test_setup_status_includes_branding(client: AsyncClient):
    # 1. Initialize instance
    setup_res = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Brand Master",
        "admin_email": "brand@example.com",
        "admin_password": "superpassword123",
        "business_name": "Luxury Silk Ltd",
        "currency": "NGN",
        "logo_url": "https://images.example.com/logo.png",
        "email_provider": "resend",
        "email_config": {
            "api_key": "re_live_secret12345",
            "from_email": "orders@luxurysilk.ng",
            "from_name": "Luxury Silk",
        },
    })
    assert setup_res.status_code == 200
    assert setup_res.json()["business"]["name"] == "Luxury Silk Ltd"
    assert setup_res.json()["business"]["logo_url"] == "https://images.example.com/logo.png"

    # 2. Check /setup/status public endpoint
    status_res = await client.get("/api/v1/setup/status")
    assert status_res.status_code == 200
    data = status_res.json()
    assert data["initialized"] is True
    assert data["business_name"] == "Luxury Silk Ltd"
    assert data["logo_url"] == "https://images.example.com/logo.png"
    assert data["business"]["name"] == "Luxury Silk Ltd"


@pytest.mark.asyncio
async def test_forgot_password_and_reset_password_flow(client: AsyncClient, db_session: AsyncSession):
    # 1. Setup instance with Resend email configured
    await client.post("/api/v1/setup/initialize", json={
        "admin_name": "John Doe",
        "admin_email": "john@example.com",
        "admin_password": "originalpassword123",
        "business_name": "Apex NG",
        "email_provider": "resend",
        "email_config": {
            "api_key": "re_test_apikey12345",
            "from_email": "noreply@apex.ng",
            "from_name": "Apex Support",
        },
    })

    # 2. Mock EmailService.send_email
    with patch("app.services.email.EmailService.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        # Request forgot password
        forgot_res = await client.post("/api/v1/auth/forgot-password", json={
            "email": "john@example.com",
        })
        assert forgot_res.status_code == 200
        assert mock_send.called
        assert mock_send.call_args[1]["to_email"] == "john@example.com"
        assert "Reset your password" in mock_send.call_args[1]["subject"]

    # 3. Generate token and test reset-password
    setup_user_res = await db_session.execute(select(AdminUser).where(AdminUser.id == 1))
    db_user = setup_user_res.scalar_one()
    token = create_password_reset_jwt(1, "john@example.com", password_hash=db_user.password_hash, expires_minutes=15)
    
    reset_res = await client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "password": "brandnewpassword456",
    })
    assert reset_res.status_code == 200

    # 4. Attempting to use the SAME token again must FAIL (token expired upon use)
    reuse_res = await client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "password": "anotherpassword789",
    })
    assert reuse_res.status_code == 400
    assert "already been used" in reuse_res.json()["detail"]

    # 5. Old password should fail
    old_login = await client.post("/api/v1/auth/login", json={
        "email": "john@example.com",
        "password": "originalpassword123",
    })
    assert old_login.status_code == 401

    # 6. New password should succeed
    new_login = await client.post("/api/v1/auth/login", json={
        "email": "john@example.com",
        "password": "brandnewpassword456",
    })
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


@pytest.mark.asyncio
async def test_settings_email_crud_and_test_send(client: AsyncClient):
    # Setup instance
    setup = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Admin Tester",
        "admin_email": "admin@example.com",
        "admin_password": "supersecretpassword123",
        "business_name": "Test Hub",
    })
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. GET /settings/email (initially empty)
    res_get = await client.get("/api/v1/settings/email", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["configured"] is False

    # 2. PUT /settings/email with Brevo config
    res_put = await client.put("/api/v1/settings/email", headers=headers, json={
        "provider": "brevo",
        "config": {
            "api_key": "xkeysib-1234567890abcdef",
            "from_email": "support@testhub.ng",
            "from_name": "Test Hub Admin",
        }
    })
    assert res_put.status_code == 200
    assert res_put.json()["configured"] is True
    assert res_put.json()["provider"] == "brevo"

    # 3. POST /settings/email/test
    with patch("app.services.email.EmailService.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        test_res = await client.post("/api/v1/settings/email/test", headers=headers, json={
            "to_email": "admin@example.com",
        })
        assert test_res.status_code == 200
        assert mock_send.called
        assert mock_send.call_args[1]["to_email"] == "admin@example.com"


@pytest.mark.asyncio
async def test_settings_payments_crud(client: AsyncClient):
    # Setup instance
    setup = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Admin Tester",
        "admin_email": "admin@example.com",
        "admin_password": "supersecretpassword123",
        "business_name": "Test Hub",
    })
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Initial GET /settings/payments (unconfigured)
    res_get = await client.get("/api/v1/settings/payments", headers=headers)
    assert res_get.status_code == 200
    data = res_get.json()
    assert "provider" in data
    assert "configured" in data
    assert "config" in data

    # 2. PUT /settings/payments (configure Paystack as single active gateway)
    res_put = await client.put("/api/v1/settings/payments", headers=headers, json={
        "provider": "paystack",
        "config": {
            "secret_key": "sk_live_1234567890abcdef",
            "public_key": "pk_live_12345",
        }
    })
    assert res_put.status_code == 200
    saved = res_put.json()
    assert saved["provider"] == "paystack"
    assert saved["configured"] is True
    assert saved["config"]["secret_key_configured"] is True
    assert "..." in saved["config"]["secret_key_masked"]
    assert saved["config"]["public_key"] == "pk_live_12345"

    # 3. PUT /settings/payments (attempting unsupported gateway returns 400)
    res_put_unsupported = await client.put("/api/v1/settings/payments", headers=headers, json={
        "provider": "stripe",
        "config": {
            "secret_key": "sk_live_stripe_secret_key_123",
            "publishable_key": "pk_live_stripe_key",
        }
    })
    assert res_put_unsupported.status_code == 400
    assert "Unsupported payment gateway" in res_put_unsupported.json()["detail"]

    # 4. PUT /settings/payments (disable payment links)
    res_put_none = await client.put("/api/v1/settings/payments", headers=headers, json={
        "provider": "none",
        "config": {}
    })
    assert res_put_none.status_code == 200
    saved_none = res_put_none.json()
    assert saved_none["provider"] is None
    assert saved_none["configured"] is False


@pytest.mark.asyncio
async def test_change_password_endpoint(client: AsyncClient):
    # 1. Setup instance
    setup = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Change Pass User",
        "admin_email": "admin_change@example.com",
        "admin_password": "InitialPassword123!",
        "business_name": "Secure Biz",
    })
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Attempt with wrong current password -> 400
    bad_res = await client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "WrongPassword!",
        "new_password": "NewSecurePassword456!",
    })
    assert bad_res.status_code == 400
    assert "Current password is incorrect" in bad_res.json()["detail"]

    # 3. Successful password change
    good_res = await client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "InitialPassword123!",
        "new_password": "NewSecurePassword456!",
    })
    assert good_res.status_code == 200
    assert good_res.json()["status"] == "ok"

    # 4. Verify login works with the new password
    login_new = await client.post("/api/v1/auth/login", json={
        "email": "admin_change@example.com",
        "password": "NewSecurePassword456!",
    })
    assert login_new.status_code == 200
    assert "access_token" in login_new.json()

    # 5. Verify old password no longer works
    login_old = await client.post("/api/v1/auth/login", json={
        "email": "admin_change@example.com",
        "password": "InitialPassword123!",
    })
    assert login_old.status_code == 401


@pytest.mark.asyncio
async def test_team_member_invite_and_role_edit(client: AsyncClient):
    # 1. Setup instance with Resend email configured
    setup = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Admin Team Lead",
        "admin_email": "teamlead@example.com",
        "admin_password": "TeamLeadPass123!",
        "business_name": "Invite Corp",
        "email_provider": "resend",
        "email_config": {
            "api_key": "re_test_key_12345",
            "from_email": "noreply@invitecorp.com",
            "from_name": "Invite Corp Support",
        },
    })
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Invite team member without password (mock email delivery)
    with patch("app.services.email.EmailService.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        invite_res = await client.post("/api/v1/users", headers=headers, json={
            "name": "Sarah Connor",
            "email": "sarah@example.com",
            "role": "operator",
        })
        assert invite_res.status_code == 201
        data = invite_res.json()
        assert data["email"] == "sarah@example.com"
        assert data["role"] == "operator"
        assert data["invited"] is True
        user_id = data["id"]

        assert mock_send.called
        assert mock_send.call_args[1]["to_email"] == "sarah@example.com"
        assert "invited" in mock_send.call_args[1]["subject"].lower()

    # 3. Edit member role: upgrade operator to admin
    update_res = await client.put(f"/api/v1/users/{user_id}", headers=headers, json={
        "name": "Sarah Connor",
        "role": "admin",
        "is_active": True,
    })
    assert update_res.status_code == 200
    updated_data = update_res.json()
    assert updated_data["role"] == "admin"

    # 4. Verify in users list
    list_res = await client.get("/api/v1/users", headers=headers)
    assert list_res.status_code == 200
    users_list = list_res.json()
    sarah = next((u for u in users_list if u["email"] == "sarah@example.com"), None)
    assert sarah is not None
    assert sarah["role"] == "admin"


@pytest.mark.asyncio
async def test_settings_validation_rejections(client: AsyncClient):
    # 1. Setup instance
    setup = await client.post("/api/v1/setup/initialize", json={
        "admin_name": "Validation Admin",
        "admin_email": "admin_val@example.com",
        "admin_password": "ValidationPassword123!",
        "business_name": "Val Corp",
    })
    token = setup.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # --- EMAIL VALIDATION ---
    # Resend without API key -> 400
    bad_resend = await client.put("/api/v1/settings/email", headers=headers, json={
        "provider": "resend",
        "config": {
            "api_key": "",
            "from_email": "hello@valcorp.ng",
        }
    })
    assert bad_resend.status_code == 400
    assert "API Key is required" in bad_resend.json()["detail"]

    # Resend with invalid/missing from_email -> 400
    bad_resend_email = await client.put("/api/v1/settings/email", headers=headers, json={
        "provider": "resend",
        "config": {
            "api_key": "re_some_valid_looking_key",
            "from_email": "invalid_email_no_at",
        }
    })
    assert bad_resend_email.status_code == 400
    assert "valid sender email" in bad_resend_email.json()["detail"]

    # --- STORAGE VALIDATION ---
    # Cloudinary without API key or cloud_name -> 400
    bad_cloudinary = await client.put("/api/v1/settings/storage", headers=headers, json={
        "provider": "cloudinary",
        "config": {
            "cloud_name": "",
            "api_key": "",
            "api_secret": "",
        }
    })
    assert bad_cloudinary.status_code == 400
    assert "Cloud Name is required" in bad_cloudinary.json()["detail"]

    # Cloudflare R2 without bucket_name -> 400
    bad_r2 = await client.put("/api/v1/settings/storage", headers=headers, json={
        "provider": "cloudflare_r2",
        "config": {
            "account_id": "acc123",
            "access_key_id": "key123",
            "secret_access_key": "sec123",
            "bucket_name": "",
        }
    })
    assert bad_r2.status_code == 400
    assert "Bucket Name is required" in bad_r2.json()["detail"]

    # --- PAYMENT GATEWAY VALIDATION ---
    # Paystack without secret key -> 400
    bad_paystack = await client.put("/api/v1/settings/payments", headers=headers, json={
        "provider": "paystack",
        "config": {
            "secret_key": "",
            "public_key": "pk_test_123",
        }
    })
    assert bad_paystack.status_code == 400
    assert "Secret Key is required" in bad_paystack.json()["detail"]

    # Unsupported gateway (e.g. Flutterwave / Monnify) -> 400
    bad_monnify = await client.put("/api/v1/settings/payments", headers=headers, json={
        "provider": "monnify",
        "config": {
            "api_key": "MK_123",
            "secret_key": "sec_123",
        }
    })
    assert bad_monnify.status_code == 400
    assert "Unsupported payment gateway" in bad_monnify.json()["detail"]

    # --- BUSINESS PROFILE VALIDATION ---
    # Empty business name -> 400
    bad_name = await client.put("/api/v1/settings/profile", headers=headers, json={
        "name": "   ",
    })
    assert bad_name.status_code == 400
    assert "Business name cannot be empty" in bad_name.json()["detail"]

    # Empty currency -> 400
    bad_curr = await client.put("/api/v1/settings/profile", headers=headers, json={
        "currency": "   ",
    })
    assert bad_curr.status_code == 400
    assert "Business currency cannot be empty" in bad_curr.json()["detail"]




