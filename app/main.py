import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import init_db, get_db
from app.core.logger import logger
from app.core.rate_limit import limiter
from app.core.security import verify_dashboard_auth
from app.commerce.storage.manager import StorageManager
from app.channels.whatsapp.webhook import router as whatsapp_router
from app.channels.telegram.webhook import router as telegram_router
from app.channels.widget.endpoints import router as widget_router
from app.commerce.payments.webhooks import router as payments_router
from app.commerce.bumpa.webhook import router as bumpa_router
from app.commerce.catalog_upload import router as catalog_upload_router
from app.telemetry.sync_worker import router as sync_router, start_sync_scheduler, shutdown_sync_scheduler
from app.telemetry.client import telemetry_client
from app.models.catalog import CatalogItem
from app.models.order import Order

WIDGET_BUNDLE_PATH = os.path.join(os.path.dirname(__file__), "..", "widget", "dist", "widget.js")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database Schema
    await init_db()

    # 2. Start Background 30m Sync Scheduler
    start_sync_scheduler()

    logger.info(f"AICB Assistant is active and ready (Mode: {settings.BOT_MODE.upper()})")

    yield

    # Shutdown hooks
    shutdown_sync_scheduler()
    telemetry_client.close()
    logger.info(f"AICB Assistant shut down gracefully.")


app = FastAPI(
    title=settings.APP_NAME,
    description="Modular Plug-and-Play AI & Interactive Chatbot Engine for WhatsApp, Telegram, Payments & Commerce",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root & Health Endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "mode": settings.BOT_MODE,
        "llm_provider": settings.LLM_PROVIDER,
        "catalog_source": settings.CATALOG_SOURCE,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "docs_url": "/docs",
        "health": "/health",
    }


def _mask_key(key: str | None) -> str | None:
    """Returns a masked preview of a secret key: first 12 chars + ... + last 4 chars."""
    if not key:
        return None
    if len(key) <= 16:
        return key[:4] + "..." + key[-2:]
    return key[:12] + "..." + key[-4:]


@app.get("/api/v1/gateway-info", tags=["Gateway"])
async def gateway_info(_: None = Depends(verify_dashboard_auth)):
    """Returns masked key previews and active gateway configuration for the AgentOS dashboard."""
    return {
        "active_gateway": settings.DEFAULT_PAYMENT_GATEWAY,
        "bot_domain": settings.BOT_DOMAIN,
        "paystack": {
            "configured": bool(settings.PAYSTACK_SECRET_KEY),
            "secret_key_preview": _mask_key(settings.PAYSTACK_SECRET_KEY),
            "public_key_preview": _mask_key(settings.PAYSTACK_PUBLIC_KEY),
        },
        "flutterwave": {
            "configured": bool(settings.FLUTTERWAVE_SECRET_KEY),
            "secret_key_preview": _mask_key(settings.FLUTTERWAVE_SECRET_KEY),
            "public_key_preview": _mask_key(settings.FLUTTERWAVE_PUBLIC_KEY),
        },
        "monnify": {
            "configured": bool(settings.MONNIFY_API_KEY),
            "api_key_preview": _mask_key(settings.MONNIFY_API_KEY),
        },
        "stripe": {
            "configured": bool(settings.STRIPE_SECRET_KEY),
            "secret_key_preview": _mask_key(settings.STRIPE_SECRET_KEY),
        },
        "storage": {
            "provider": settings.STORAGE_PROVIDER,
            "configured": StorageManager.is_configured(),
            "cloudinary": {
                "configured": bool(settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_CLOUD_NAME),
                "cloud_name": settings.CLOUDINARY_CLOUD_NAME,
                "api_key_preview": _mask_key(settings.CLOUDINARY_API_KEY),
                "folder": settings.CLOUDINARY_FOLDER,
            },
            "cloudflare_r2": {
                "configured": bool(settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID),
                "account_id": settings.R2_ACCOUNT_ID,
                "bucket_name": settings.R2_BUCKET_NAME,
                "access_key_preview": _mask_key(settings.R2_ACCESS_KEY_ID),
                "public_url": settings.R2_PUBLIC_URL,
            },
        },
    }


# Include Routers under /api/v1
app.include_router(whatsapp_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")
app.include_router(widget_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(bumpa_router, prefix="/api/v1")
app.include_router(catalog_upload_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")


@app.get("/widget.js", tags=["Website Widget"])
async def widget_bundle():
    """Serves the embeddable widget script. Businesses install it via
    <script src="{instanceUrl}/widget.js" data-bot-id="..."></script>."""
    if not os.path.isfile(WIDGET_BUNDLE_PATH):
        raise HTTPException(status_code=404, detail="Widget bundle not built for this instance yet.")
    return FileResponse(WIDGET_BUNDLE_PATH, media_type="application/javascript")


# Dashboard-Facing Endpoints (require Authorization: Bearer <AICB_API_KEY>)
@app.get("/api/v1/catalog", tags=["Catalog"])
async def list_catalog_items(db: AsyncSession = Depends(get_db), _: None = Depends(verify_dashboard_auth)):
    stmt = select(CatalogItem).limit(50)
    res = await db.execute(stmt)
    return res.scalars().all()


@app.get("/api/v1/orders", tags=["Orders"])
async def list_orders(db: AsyncSession = Depends(get_db), _: None = Depends(verify_dashboard_auth)):
    stmt = select(Order).order_by(Order.created_at.desc()).limit(20)
    res = await db.execute(stmt)
    return res.scalars().all()
