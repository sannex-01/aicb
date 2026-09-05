from typing import Optional
from app.ai.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from app.ai.providers.gemini import GeminiProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.providers.claude import ClaudeProvider
from app.core.config import settings


def get_llm_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None) -> BaseLLMProvider:
    """Factory to retrieve the active LLM provider instance."""
    provider = (provider_name or settings.LLM_PROVIDER).lower()

    if provider in ["gemini", "google"]:
        return GeminiProvider(api_key=api_key)
    elif provider in ["openai", "groq", "deepseek"]:
        return OpenAIProvider(api_key=api_key)
    elif provider in ["claude", "anthropic"]:
        return ClaudeProvider(api_key=api_key)
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}. Choose 'gemini', 'openai', or 'claude'.")


__all__ = [
    "BaseLLMProvider",
    "LLMResponse",
    "ToolCall",
    "GeminiProvider",
    "OpenAIProvider",
    "ClaudeProvider",
    "get_llm_provider",
]
