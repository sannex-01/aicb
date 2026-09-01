import json
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.commerce.catalog_provider import CatalogManager
from app.commerce.payments.unified import UnifiedPaymentManager
from app.channels.slack.client import SlackDispatcher
from app.channels.slack.fallback import get_support_contact_message
from app.models.order import Order
from app.core.logger import logger


TOOL_DEFINITIONS = [
    {
        "name": "search_catalog",
        "description": "Searches for products or services in the catalog by keyword, name, or category.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search keyword or product name (e.g. 'shoes', 'iphone', 'consulting')",
                },
                "category": {
                    "type": "string",
                    "description": "Optional category filter",
                },
            },
        },
    },
    {
        "name": "create_order",
        "description": "Creates an order for the customer with chosen products.",
        "parameters": {
            "type": "object",
            "properties": {
                "items": {
                    "type": "array",
                    "description": "List of items to order with id or title, and quantity",
                    "items": {
                        "type": "object",
                        "properties": {
                            "product_id": {"type": "integer"},
                            "title": {"type": "string"},
                            "quantity": {"type": "integer"},
                            "price": {"type": "number"},
                        },
                        "required": ["title", "quantity", "price"],
                    },
                },
                "customer_name": {"type": "string", "description": "Customer full name"},
                "customer_phone": {"type": "string", "description": "Customer phone number"},
                "customer_email": {"type": "string", "description": "Customer email address"},
                "shipping_address": {"type": "string", "description": "Customer delivery address if applicable"},
            },
            "required": ["items"],
        },
    },
    {
        "name": "generate_payment_link",
        "description": "Generates a secure online payment checkout link for an order using Paystack, Flutterwave, Monnify, or Stripe.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_reference": {
                    "type": "string",
                    "description": "The unique reference of the created order (e.g. 'ORD-123456')",
                },
                "gateway": {
                    "type": "string",
                    "description": "Optional payment gateway: 'paystack', 'flutterwave', 'monnify', or 'stripe'",
                },
            },
            "required": ["order_reference"],
        },
    },
    {
        "name": "get_order_status",
        "description": "Checks the status of an existing customer order by order reference.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_reference": {
                    "type": "string",
                    "description": "The order reference code (e.g. 'ORD-123456')",
                },
            },
            "required": ["order_reference"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": "Escalates the conversation to human support staff when the customer requests an agent or has an unresolvable issue.",
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Why human assistance is required"},
                "urgency": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Urgency level",
                },
            },
            "required": ["reason"],
        },
    },
]


class ToolExecutor:
    """Executes AI tool calls against the database, commerce layer, and channels."""

    @staticmethod
    async def execute(
        db: AsyncSession,
        name: str,
        arguments: Dict[str, Any],
        customer_identifier: str,
        channel: str,
    ) -> Dict[str, Any]:
        logger.info(f"Executing tool {name} with args: {arguments}")

        if name == "search_catalog":
            query = arguments.get("query")
            category = arguments.get("category")
            items = await CatalogManager.search_products(db, query=query, category=category, limit=8)
            if not items:
                return {"results": [], "message": "No matching products found."}

            return {
                "results": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "description": item.description,
                        "price": item.price,
                        "currency": item.currency,
                        "in_stock": item.in_stock,
                    }
                    for item in items
                ]
            }

        elif name == "create_order":
            items = arguments.get("items", [])
            if not items:
                return {"error": "Order items list cannot be empty."}

            total_amount = sum(float(item.get("price", 0)) * int(item.get("quantity", 1)) for item in items)
            order_ref = f"ORD-{uuid.uuid4().hex[:8].upper()}"

            order = Order(
                order_reference=order_ref,
                customer_identifier=customer_identifier,
                channel=channel,
                items_json=json.dumps(items),
                total_amount=total_amount,
                currency="NGN",
                customer_name=arguments.get("customer_name"),
                customer_phone=arguments.get("customer_phone"),
                customer_email=arguments.get("customer_email") or f"{customer_identifier.replace('+', '')}@example.com",
                shipping_address=arguments.get("shipping_address"),
                status="pending",
            )
            db.add(order)
            await db.commit()
            await db.refresh(order)

            return {
                "order_reference": order_ref,
                "total_amount": total_amount,
                "currency": order.currency,
                "status": "pending",
                "message": f"Order {order_ref} created successfully. Total: {total_amount:,.2f} {order.currency}.",
            }

        elif name == "generate_payment_link":
            order_ref = arguments.get("order_reference")
            gateway = arguments.get("gateway")

            stmt = select(Order).where(Order.order_reference == order_ref)
            result = await db.execute(stmt)
            order = result.scalars().first()

            if not order:
                return {"error": f"Order {order_ref} not found."}

            email = order.customer_email or f"customer_{customer_identifier.replace('+', '')}@example.com"

            try:
                payment_res = await UnifiedPaymentManager.create_payment_link(
                    amount=order.total_amount,
                    currency=order.currency,
                    customer_email=email,
                    reference=order.order_reference,
                    gateway=gateway,
                    customer_name=order.customer_name,
                    customer_phone=order.customer_phone,
                )
                checkout_url = payment_res.get("checkout_url")
                order.checkout_url = checkout_url
                order.payment_gateway = gateway or "default"
                await db.commit()

                return {
                    "order_reference": order_ref,
                    "amount": order.total_amount,
                    "currency": order.currency,
                    "checkout_url": checkout_url,
                    "message": f"Please complete your payment of {order.total_amount:,.2f} {order.currency} via this secure link: {checkout_url}",
                }
            except Exception as e:
                logger.error(f"Payment link creation error: {e}")
                return {"error": f"Could not generate payment link: {str(e)}"}

        elif name == "get_order_status":
            order_ref = arguments.get("order_reference")
            stmt = select(Order).where(Order.order_reference == order_ref)
            result = await db.execute(stmt)
            order = result.scalars().first()

            if not order:
                return {"error": f"No order found with reference {order_ref}."}

            return {
                "order_reference": order.order_reference,
                "status": order.status,
                "total_amount": order.total_amount,
                "currency": order.currency,
                "created_at": order.created_at.isoformat() if order.created_at else None,
            }

        elif name == "escalate_to_human":
            reason = arguments.get("reason", "Customer requested assistance")
            urgency = arguments.get("urgency", "medium")

            # Post to Slack if configured
            await SlackDispatcher.dispatch_escalation(
                customer_identifier=customer_identifier,
                channel=channel,
                reason=reason,
                urgency=urgency,
            )

            # Return fallback contact info for AI to include in customer reply
            support_card = get_support_contact_message()
            return {
                "status": "escalated",
                "support_message": support_card,
            }

        else:
            return {"error": f"Unknown tool: {name}"}
