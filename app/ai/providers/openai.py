import json
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from app.ai.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from app.core.config import settings
from app.core.logger import logger


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT LLM Provider with tool calling support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ) -> LLMResponse:
        model = model_name or settings.OPENAI_MODEL

        formatted_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            formatted_messages.append({
                "role": msg["role"],
                "content": msg.get("content", ""),
            })

        formatted_tools = None
        if tools:
            formatted_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("parameters", {}),
                    }
                }
                for t in tools
            ]

        try:
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": formatted_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            if formatted_tools:
                kwargs["tools"] = formatted_tools

            response = await self.client.chat.completions.create(**kwargs)
            choice = response.choices[0]
            message = choice.message

            tool_calls: List[ToolCall] = []
            if message.tool_calls:
                for tc in message.tool_calls:
                    try:
                        args = json.loads(tc.function.arguments)
                    except Exception:
                        args = {}
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        name=tc.function.name,
                        arguments=args,
                    ))

            return LLMResponse(
                content=message.content,
                tool_calls=tool_calls if tool_calls else None,
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise
