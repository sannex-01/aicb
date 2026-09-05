import os
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings
from app.core.logger import logger

# Check dialect and format correctly for async driver
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite:///"):
    db_url = db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
elif db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+asyncpg://")

connect_args = {"check_same_thread": False} if "sqlite" in db_url else {}

engine = create_async_engine(
    db_url,
    echo=False,
    connect_args=connect_args,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


from sqlalchemy import text, inspect


def _sync_columns(sync_conn) -> None:
    """Safely adds newly defined columns to existing tables if they do not exist."""
    inspector = inspect(sync_conn)
    existing_tables = set(inspector.get_table_names())

    migrations = [
        # (table_name, column_name, column_type_sql, default_sql)
        ("agents", "group_ids_json", "TEXT", "'[]'"),
        ("agents", "access_tags_json", "TEXT", "'[]'"),
        ("agents", "api_key_override", "VARCHAR(255)", "NULL"),
        ("agents", "widget_enabled", "BOOLEAN", "TRUE"),
        ("agents", "widget_profile_collection", "VARCHAR(50)", "'upfront'"),
        ("agents", "whatsapp_phone_number_id", "VARCHAR(100)", "NULL"),
        ("agents", "whatsapp_access_token", "VARCHAR(255)", "NULL"),
        ("agents", "telegram_bot_token", "VARCHAR(255)", "NULL"),
        ("agents", "telegram_username", "VARCHAR(100)", "NULL"),
        ("agents", "group_id", "INTEGER", "NULL"),
        ("access_groups", "llm_provider", "VARCHAR(50)", "NULL"),
        ("access_groups", "api_key", "VARCHAR(255)", "NULL"),
        ("access_groups", "model_name", "VARCHAR(100)", "NULL"),
        ("access_groups", "tags_json", "TEXT", "'[]'"),
        ("catalog_items", "access_group_ids_json", "TEXT", "'[]'"),
        ("catalog_items", "access_tags_json", "TEXT", "'[]'"),
        ("knowledge_docs", "access_tags_json", "TEXT", "'[]'"),
    ]

    for table_name, col_name, col_type, default_val in migrations:
        if table_name in existing_tables:
            existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            if col_name not in existing_cols:
                try:
                    default_clause = f" DEFAULT {default_val}" if default_val != "NULL" else ""
                    sync_conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}{default_clause}"))
                    logger.info(f"Auto-migrated: Added column '{col_name}' to '{table_name}' table.")
                except Exception as e:
                    logger.warning(f"Could not auto-add column '{col_name}' to '{table_name}': {e}")


async def init_db() -> None:
    """Initialize database tables and run automatic column sync."""
    logger.info("Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_sync_columns)
    logger.info("Database schema initialized successfully.")
