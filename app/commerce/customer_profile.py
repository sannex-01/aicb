import re
from typing import Optional
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
