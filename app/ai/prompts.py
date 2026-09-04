from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.models.config_override import ConfigOverride


async def get_system_prompt(
    db: AsyncSession,
    customer_name: Optional[str] = None,
    channel: Optional[str] = None,
    rag_context: Optional[str] = None,
) -> str:
    """Builds the comprehensive system prompt combining baseline, dynamic overrides, and RAG knowledge."""
    # Check for AgentOS synced prompt override
    stmt = select(ConfigOverride).where(ConfigOverride.key == "system_prompt")
    result = await db.execute(stmt)
    override = result.scalars().first()

    base_prompt = override.value if override else settings.DEFAULT_SYSTEM_PROMPT

    context_parts = [base_prompt]

    # Add channel & customer context
    customer_info = f"- Channel: {channel.upper() if channel else 'Unknown'}"
    if customer_name:
        customer_info += f"\n- Customer Name: {customer_name}"
    context_parts.append(f"\n[Customer Context]\n{customer_info}")

    # Add RAG Knowledge Base if available
    if rag_context:
        context_parts.append(
            f"\n[Verified Business Knowledge Base]\n"
            f"Use the following official information to answer the customer's inquiries accurately:\n"
            f"{rag_context}"
        )

    # Guidelines
    context_parts.append(
        "\n[Operational Guidelines]\n"
        "1. When customers ask for product recommendations or catalog items, use the `search_catalog` tool.\n"
        "2. When a customer confirms which item(s) and quantity they want, call `create_order` immediately — do NOT ask them for their name, email, or phone number yourself; that is handled entirely outside this conversation. If those details are still needed, `create_order`'s result will say so and the customer will be prompted directly by the system, not by you — just wait for their next message and try again.\n"
        "3. When ready for checkout, use `generate_payment_link` tool and share the link with the customer.\n"
        "4. If a customer is frustrated, requests human assistance, or has a critical issue, use `escalate_to_human`.\n"
        "5. Keep responses concise, formatted with clear bullet points, and friendly.\n"
        "6. IMPORTANT: When providing a payment link or any actionable URL, ALWAYS format it as a Markdown link (e.g. `[Pay Now](https://...)` or `[View Catalog](https://...)`). The system will parse this into interactive buttons."
    )

    return "\n".join(context_parts)
