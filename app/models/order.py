from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text
from app.core.database import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_reference = Column(String(100), unique=True, index=True, nullable=False)
    customer_identifier = Column(String(100), nullable=False, index=True)
    channel = Column(String(50), nullable=False) # whatsapp, telegram
    
    items_json = Column(Text, nullable=False, default="[]") # List of [{id, title, qty, price}]
    total_amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), default="NGN")
    
    shipping_address = Column(Text, nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(50), nullable=True)
    customer_email = Column(String(255), nullable=True)
    
    status = Column(String(50), default="pending", index=True) # pending, paid, processing, completed, cancelled
    payment_gateway = Column(String(50), nullable=True) # paystack, flutterwave, monnify, stripe, telegram, bumpa
    payment_reference = Column(String(150), nullable=True, index=True)
    checkout_url = Column(String(500), nullable=True)
    metadata_json = Column(Text, default="{}")

    # Set when a single cart had to be split into separate orders/payments
    # because its items route to different gateways (e.g. Bumpa-sourced
    # items must checkout through Bumpa's own cart+payment-intent flow,
    # while everything else uses the business's normal gateway) — every
    # sibling order shares the same group_reference so they can be
    # reassembled for the customer's order history / a single receipt.
    group_reference = Column(String(100), nullable=True, index=True)

    # Real fulfillment status columns — previously only ever written into
    # metadata_json["fulfillment_status"] by FulfillmentManager and never
    # read back anywhere (a write-only field). fulfillment_status:
    # "pending" | "dispatched" | "delivered_digital" | "shipped" |
    # "delivered" | "failed" | "manual" — see FulfillmentManager for the
    # actual transitions. tracking_url/courier_name are populated once a
    # real courier booking exists (Terminal Africa integration, not yet
    # built) — both stay null for digital/service/manual orders.
    fulfillment_status = Column(String(30), nullable=True, index=True)
    tracking_url = Column(String(500), nullable=True)
    courier_name = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


class PaymentLog(Base):
    __tablename__ = "payment_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_reference = Column(String(100), index=True, nullable=False)
    gateway = Column(String(50), nullable=False)
    gateway_reference = Column(String(150), index=True, nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="NGN")
    status = Column(String(50), nullable=False) # success, failed, pending
    payload_json = Column(Text, default="{}")
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
