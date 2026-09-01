from typing import List, Dict, Any, Optional
from anthropic import AsyncAnthropic
from app.ai.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from app.core.config import settings
from app.core.logger import logger


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude LLM Provider with tool use support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        self.client = AsyncAnthropic(api_key=self.api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ) -> LLMResponse:
        model = model_name or settings.ANTHROPIC_MODEL

        formatted_messages = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "tool"] else "assistant"
            content_text = msg.get("content", "")
            if msg.get("role") == "tool":
                content_text = f"[Tool Result]: {content_text}"
            formatted_messages.append({
                "role": role,
                "content": content_text,
            })

        formatted_tools = None
        if tools:
            formatted_tools = [
                {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
                }
                for t in tools
            ]

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system_prompt,
                "messages": formatted_messages,
            }
            if formatted_tools:
                kwargs["tools"] = formatted_tools

            response = await self.client.messages.create(**kwargs)

            tool_calls: List[ToolCall] = []
            content_text = ""

            for block in response.content:
                if block.type == "text":
                    content_text += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        name=block.name,
                        arguments=block.input if isinstance(block.input, dict) else {},
                    ))

            return LLMResponse(
                content=content_text if content_text else None,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=response.stop_reason,
            )
        except Exception as e:
            logger.error(f"Claude generation error: {e}")
            raise
