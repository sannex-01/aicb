import json
from typing import Dict, Any, Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.ai.providers import get_llm_provider
from app.ai.providers.base import LLMResponse, ToolCall
from app.ai.prompts import get_system_prompt
from app.ai.rag import RAGEngine
from app.ai.memory import MemoryManager
from app.ai.tools import TOOL_DEFINITIONS, ToolExecutor, PROFILE_COLLECT_SENTINEL
from app.models.session import ConversationSession
from app.models.config_override import ConfigOverride
from app.core.config import settings
from app.core.logger import logger
from app.schemas.bot_response import BotResponse, ProductCard


class AIOrchestrator:
    """Coordinates Multi-LLM inference, RAG context, sliding memory, and tool execution."""

    @staticmethod
    async def process_message(
        db: AsyncSession,
        channel: str,
        customer_identifier: str,
        user_message: str,
        customer_name: Optional[str] = None,
    ) -> BotResponse:
        # 1. Get or create session & memory
        session = await MemoryManager.get_or_create_session(
            db, channel=channel, customer_identifier=customer_identifier
        )

        # 2. Check for dynamic config overrides synced from AgentOS
        stmt = select(ConfigOverride)
        res = await db.execute(stmt)
        overrides = {row.key: row.value for row in res.scalars().all()}

        provider_name = overrides.get("llm_provider", settings.LLM_PROVIDER)
        model_name = overrides.get("model_name")
        temperature = float(overrides.get("temperature", settings.LLM_TEMPERATURE))
        max_tokens = int(overrides.get("max_tokens", settings.LLM_MAX_TOKENS))

        # 3. Retrieve relevant knowledge base chunks via RAG
        rag_context = await RAGEngine.retrieve_relevant_context(db, query=user_message, top_k=3)

        # 4. Compose dynamic system prompt
        system_prompt = await get_system_prompt(
            db,
            customer_name=customer_name,
            channel=channel,
            rag_context=rag_context if rag_context else None,
        )

        # 5. Build conversation history
        history = MemoryManager.get_history(session)
        messages: List[Dict[str, Any]] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]
        # Append current user message
        messages.append({"role": "user", "content": user_message})

        # 6. Execute LLM with tool calling loop
        provider = get_llm_provider(provider_name)

        max_tool_iterations = 4
        current_iteration = 0
        final_reply = ""
        tool_execution_logs: List[Dict[str, Any]] = []
        collected_product_cards: List[Dict[str, Any]] = []
        collected_checkout_url: Optional[str] = None

        while current_iteration < max_tool_iterations:
            current_iteration += 1

            llm_response: LLMResponse = await provider.generate_response(
                messages=messages,
                system_prompt=system_prompt,
                tools=TOOL_DEFINITIONS,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
            )

            # If tool calls were made, execute them
            if llm_response.tool_calls:
                # Add assistant turn with tool calls to local history
                assistant_tool_msg = {
                    "role": "assistant",
                    "content": llm_response.content or "Let me check that for you.",
                }
                messages.append(assistant_tool_msg)

                profile_collect_prompt: Optional[str] = None
                for tc in llm_response.tool_calls:
                    tool_result = await ToolExecutor.execute(
                        db=db,
                        name=tc.name,
                        arguments=tc.arguments,
                        customer_identifier=customer_identifier,
                        channel=channel,
                    )

                    if isinstance(tool_result, dict) and PROFILE_COLLECT_SENTINEL in tool_result:
                        # A required customer profile is missing — stop the tool loop
                        # immediately and surface the collection prompt verbatim,
                        # rather than letting the LLM see/paraphrase it.
                        profile_collect_prompt = tool_result[PROFILE_COLLECT_SENTINEL]
                        break

                    tool_execution_logs.append({
                        "name": tc.name,
                        "args": tc.arguments,
                        "result": tool_result,
                    })

                    presentation = tool_result.get("presentation") if isinstance(tool_result, dict) else None
                    if presentation:
                        collected_product_cards.extend(presentation.get("product_cards", []))
                        if presentation.get("checkout_url"):
                            collected_checkout_url = presentation["checkout_url"]

                    # Append tool result to messages for next LLM iteration
                    messages.append({
                        "role": "tool",
                        "name": tc.name,
                        "content": json.dumps(tool_result),
                    })

                if profile_collect_prompt is not None:
                    final_reply = profile_collect_prompt
                    break

                # Loop to let LLM formulate final answer with tool output
                continue

            # No more tool calls, we have the final content
            final_reply = llm_response.content or "I am here to assist you. How can I help today?"
            break

        # 7. Record user and assistant messages into memory manager
        await MemoryManager.add_message(
            db=db,
            session=session,
            role="user",
            content=user_message,
        )
        await MemoryManager.add_message(
            db=db,
            session=session,
            role="assistant",
            content=final_reply,
            tool_calls=tool_execution_logs if tool_execution_logs else None,
        )

        return BotResponse(
            text=final_reply,
            product_cards=[ProductCard(**c) for c in collected_product_cards],
            checkout_url=collected_checkout_url,
        )

    @staticmethod
    async def process_message_stream(
        db: AsyncSession,
        channel: str,
        customer_identifier: str,
        user_message: str,
        customer_name: Optional[str] = None,
    ):
        session = await MemoryManager.get_or_create_session(
            db, channel=channel, customer_identifier=customer_identifier
        )

        stmt = select(ConfigOverride)
        res = await db.execute(stmt)
        overrides = {row.key: row.value for row in res.scalars().all()}

        provider_name = overrides.get("llm_provider", settings.LLM_PROVIDER)
        model_name = overrides.get("model_name")
        temperature = float(overrides.get("temperature", settings.LLM_TEMPERATURE))
        max_tokens = int(overrides.get("max_tokens", settings.LLM_MAX_TOKENS))

        rag_context = await RAGEngine.retrieve_relevant_context(db, query=user_message, top_k=3)

        system_prompt = await get_system_prompt(
            db,
            customer_name=customer_name,
            channel=channel,
            rag_context=rag_context if rag_context else None,
        )

        history = MemoryManager.get_history(session)
        messages: List[Dict[str, Any]] = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in history
        ]
        messages.append({"role": "user", "content": user_message})

        provider = get_llm_provider(provider_name)

        max_tool_iterations = 4
        current_iteration = 0
        final_reply = ""
        tool_execution_logs: List[Dict[str, Any]] = []
        collected_product_cards: List[Dict[str, Any]] = []
        collected_checkout_url: Optional[str] = None

        while current_iteration < max_tool_iterations:
            current_iteration += 1

            stream = provider.generate_stream(
                messages=messages,
                system_prompt=system_prompt,
                tools=TOOL_DEFINITIONS,
                temperature=temperature,
                max_tokens=max_tokens,
                model_name=model_name,
            )

            tool_calls = None
            async for chunk in stream:
                if isinstance(chunk, dict) and chunk.get("type") == "tool_calls":
                    tool_calls = chunk["calls"]
                elif isinstance(chunk, str):
                    final_reply += chunk
                    yield chunk

            if tool_calls:
                assistant_tool_msg = {
                    "role": "assistant",
                    "content": "Let me check that for you.",
                }
                messages.append(assistant_tool_msg)

                stream_profile_collect_prompt: Optional[str] = None
                for tc in tool_calls:
                    tool_result = await ToolExecutor.execute(
                        db=db,
                        name=tc.name,
                        arguments=tc.arguments,
                        customer_identifier=customer_identifier,
                        channel=channel,
                    )

                    if isinstance(tool_result, dict) and PROFILE_COLLECT_SENTINEL in tool_result:
                        stream_profile_collect_prompt = tool_result[PROFILE_COLLECT_SENTINEL]
                        break

                    tool_execution_logs.append({
                        "name": tc.name,
                        "args": tc.arguments,
                        "result": tool_result,
                    })

                    presentation = tool_result.get("presentation") if isinstance(tool_result, dict) else None
                    if presentation:
                        collected_product_cards.extend(presentation.get("product_cards", []))
                        if presentation.get("checkout_url"):
                            collected_checkout_url = presentation["checkout_url"]

                    messages.append({
                        "role": "tool",
                        "name": tc.name,
                        "content": json.dumps(tool_result),
                    })

                if stream_profile_collect_prompt is not None:
                    final_reply += stream_profile_collect_prompt
                    yield stream_profile_collect_prompt
                    break

                continue

            break

        await MemoryManager.add_message(
            db=db,
            session=session,
            role="user",
            content=user_message,
        )
        await MemoryManager.add_message(
            db=db,
            session=session,
            role="assistant",
            content=final_reply,
            tool_calls=tool_execution_logs if tool_execution_logs else None,
        )

        yield {
            "type": "final",
            "data": BotResponse(
                text=final_reply,
                product_cards=[ProductCard(**c) for c in collected_product_cards],
                checkout_url=collected_checkout_url,
            ),
        }
