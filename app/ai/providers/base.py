from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from pydantic import BaseModel


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: Dict[str, Any]


class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract interface for all LLM providers (Gemini, OpenAI, Claude)."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ) -> LLMResponse:
        """Generates response with optional tool calls."""
        pass

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ):
        """Yields string chunks of the final response, or returns a list of ToolCalls if it decides to call tools."""
        pass
