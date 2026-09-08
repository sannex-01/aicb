import json
import re
from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.customer import Customer

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,20}$")


def is_valid_email(value: str) -> bool:
    return bool(EMAIL_RE.match(value.strip()))


def is_valid_phone(value: str) -> bool:
    digits = re.sub(r"[^\d]", "", value)
    return bool(PHONE_RE.match(value.strip())) and 7 <= len(digits) <= 15


async def get_customer(db: AsyncSession, channel: str, identifier: str) -> Optional[Customer]:
    """Looks up a stored profile by channel identity. Widget has no persistent identity — callers must not call this for channel == 'widget'."""
    if channel == "whatsapp":
        stmt = select(Customer).where(Customer.wa_id == identifier)
    elif channel == "telegram":
        stmt = select(Customer).where(Customer.telegram_id == identifier)
    else:
        return None

    res = await db.execute(stmt)
    return res.scalars().first()


def is_profile_complete(customer: Optional[Customer]) -> bool:
    if not customer:
        return False
    return bool(customer.name and customer.email and customer.phone_number)


async def upsert_customer(
    db: AsyncSession,
    channel: str,
    identifier: str,
    name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> Optional[Customer]:
    """Creates or updates the Customer row for a WhatsApp/Telegram identity. No-op for widget."""
    if channel not in ("whatsapp", "telegram"):
        return None

    customer = await get_customer(db, channel, identifier)
    if not customer:
        customer = Customer(
            wa_id=identifier if channel == "whatsapp" else None,
            telegram_id=identifier if channel == "telegram" else None,
        )
        db.add(customer)

    if name:
        customer.name = name
    if email:
        customer.email = email
    if phone:
        customer.phone_number = phone

    await db.commit()
    await db.refresh(customer)
    return customer


def get_delivery_address(customer: Optional[Customer]) -> Optional[Dict[str, Any]]:
    """Reads the structured delivery address saved on a Customer, if any.
    Shape: {"street", "city", "state", "zip", "country"} — see
    app/commerce/address.py for the parsing that produces this."""
    if not customer or not customer.metadata_json:
        return None
    try:
        meta = json.loads(customer.metadata_json)
    except Exception:
        return None
    return meta.get("delivery_address")


async def save_delivery_address(db: AsyncSession, customer: Customer, fields: Dict[str, Any]) -> Customer:
    """Persists a structured delivery address onto a Customer row (widget
    has no durable Customer identity — callers must not call this for
    channel == 'widget'; the widget's address lives only in session
    state_data for that single checkout, same as its profile form)."""
    try:
        meta = json.loads(customer.metadata_json) if customer.metadata_json else {}
    except Exception:
        meta = {}
    meta["delivery_address"] = fields
    customer.metadata_json = json.dumps(meta)
    await db.commit()
    await db.refresh(customer)
    return customer
