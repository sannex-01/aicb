from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import init_db, get_db
from app.core.logger import logger
from app.channels.whatsapp.webhook import router as whatsapp_router
from app.channels.telegram.webhook import router as telegram_router
from app.channels.miniapp.endpoints import router as miniapp_router
from app.commerce.payments.webhooks import router as payments_router
from app.commerce.bumpa.webhook import router as bumpa_router
from app.telemetry.sync_worker import router as sync_router, start_sync_scheduler, shutdown_sync_scheduler
from app.telemetry.client import telemetry_client
from app.models.catalog import CatalogItem
from app.models.order import Order


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Initialize Database Schema
    await init_db()

    # 2. Start Background 12h Sync Scheduler
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


# Include Routers under /api/v1
app.include_router(whatsapp_router, prefix="/api/v1")
app.include_router(telegram_router, prefix="/api/v1")
app.include_router(miniapp_router, prefix="/api/v1")
app.include_router(payments_router, prefix="/api/v1")
app.include_router(bumpa_router, prefix="/api/v1")
app.include_router(sync_router, prefix="/api/v1")


# Helper Read Endpoints for Developer Verification
@app.get("/api/v1/catalog", tags=["Catalog"])
async def list_catalog_items(db: AsyncSession = Depends(get_db)):
    stmt = select(CatalogItem).limit(50)
    res = await db.execute(stmt)
    return res.scalars().all()


@app.get("/api/v1/orders", tags=["Orders"])
async def list_orders(db: AsyncSession = Depends(get_db)):
    stmt = select(Order).order_by(Order.created_at.desc()).limit(20)
    res = await db.execute(stmt)
    return res.scalars().all()
