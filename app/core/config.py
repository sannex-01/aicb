import os
from typing import Literal, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_NAME: str = "AICB Assistant"
    ENVIRONMENT: Literal["development", "production"] = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # Bot Operating Mode: 'conversational' | 'interactive_flow' | 'hybrid'
    BOT_MODE: Literal["conversational", "interactive_flow", "hybrid"] = "hybrid"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./aicb.db"

    # Memory & Session
    SESSION_EXPIRY_HOURS: int = 24
    MEMORY_WINDOW_SIZE: int = 10

    # LLM Providers & Active Setting
    LLM_PROVIDER: Literal["gemini", "openai", "claude"] = "gemini"

    # Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # OpenAI
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Claude
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # Baseline LLM Config
    LLM_TEMPERATURE: float = 0.7
    LLM_MAX_TOKENS: int = 1024
    DEFAULT_SYSTEM_PROMPT: str = (
        "You are a helpful, professional AI business assistant. You assist customers with product inquiries, "
        "order placement, payments, and general customer service. Always be concise, warm, and helpful."
    )

    # WhatsApp Cloud API (Meta)
    META_WHATSAPP_TOKEN: Optional[str] = None
    META_PHONE_NUMBER_ID: Optional[str] = None
    META_BUSINESS_ACCOUNT_ID: Optional[str] = None
    META_APP_SECRET: Optional[str] = None
    META_VERIFY_TOKEN: str = "aicb_webhook_verification_token_secret"
    WHATSAPP_FLOW_PRIVATE_KEY: Optional[str] = None
    WHATSAPP_FLOW_PRIVATE_KEY_PASSPHRASE: Optional[str] = None

    # Telegram
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    TELEGRAM_PAYMENT_PROVIDER_TOKEN: Optional[str] = None

    # Escalations & Slack
    SLACK_WEBHOOK_URL: Optional[str] = None
    SUPPORT_PHONE_NUMBER: str = "+2348000000000"
    SUPPORT_EMAIL: str = "support@example.com"

    # Catalog Provider: 'local' | 'paystack' | 'bumpa'
    CATALOG_SOURCE: Literal["local", "paystack", "bumpa"] = "local"

    # Bumpa
    BUMPA_API_KEY: Optional[str] = None
    BUMPA_STORE_ID: Optional[str] = None
    BUMPA_API_BASE_URL: str = "https://api.getbumpa.com/v1"

    # Payment Gateway Defaults
    DEFAULT_PAYMENT_GATEWAY: Literal["paystack", "flutterwave", "monnify", "stripe"] = "paystack"

    # Paystack
    PAYSTACK_SECRET_KEY: Optional[str] = None
    PAYSTACK_PUBLIC_KEY: Optional[str] = None
    PAYSTACK_CALLBACK_URL: str = "https://yourdomain.com/payments/paystack/callback"

    # Flutterwave
    FLUTTERWAVE_SECRET_KEY: Optional[str] = None
    FLUTTERWAVE_PUBLIC_KEY: Optional[str] = None
    FLUTTERWAVE_SECRET_HASH: Optional[str] = None

    # Monnify
    MONNIFY_API_KEY: Optional[str] = None
    MONNIFY_SECRET_KEY: Optional[str] = None
    MONNIFY_CONTRACT_CODE: Optional[str] = None
    MONNIFY_BASE_URL: str = "https://sandbox.monnify.com"

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_SUCCESS_URL: str = "https://yourdomain.com/payments/stripe/success"
    STRIPE_CANCEL_URL: str = "https://yourdomain.com/payments/stripe/cancel"

    # Sannex Agent Telemetry & AgentOS Sync
    SANNEX_API_KEY: Optional[str] = None
    SANNEX_HOST: str = "https://api.sannex.ng"
    SYNC_INTERVAL_HOURS: int = 12
    ENABLE_TELEMETRY: bool = True


settings = Settings()


def get_settings() -> Settings:
    return settings
