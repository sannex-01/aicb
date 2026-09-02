import json
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types
from app.ai.providers.base import BaseLLMProvider, LLMResponse, ToolCall
from app.core.config import settings
from app.core.logger import logger


class GeminiProvider(BaseLLMProvider):
    """Google Gemini LLM Provider with tool calling support."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        self.client = genai.Client(api_key=self.api_key)

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ) -> LLMResponse:
        model = model_name or settings.GEMINI_MODEL

        # Convert standard messages to Gemini contents
        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "tool"] else "model"
            content_text = msg.get("content", "")
            if msg.get("role") == "tool":
                # Represent tool output clearly in user turn
                content_text = f"[Tool Output for {msg.get('name', 'tool')}]: {content_text}"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=content_text)]
            ))

        # Format function declarations if tools provided
        gemini_tools = None
        if tools:
            declarations = []
            for t in tools:
                declarations.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                ))
            gemini_tools = [types.Tool(function_declarations=declarations)]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=gemini_tools,
        )

        try:
            # google-genai client.models.generate_content is synchronous / threaded
            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )

            tool_calls: List[ToolCall] = []
            content_text = ""

            if response.candidates:
                candidate = response.candidates[0]
                for part in candidate.content.parts:
                    if part.function_call:
                        args = part.function_call.args
                        tool_calls.append(ToolCall(
                            id=f"call_{part.function_call.name}_{len(tool_calls)}",
                            name=part.function_call.name,
                            arguments=dict(args) if args else {},
                        ))
                    elif part.text:
                        content_text += part.text

            return LLMResponse(
                content=content_text if content_text else None,
                tool_calls=tool_calls if tool_calls else None,
            )
        except Exception as e:
            logger.error(f"Gemini generation error: {e}")
            raise

    async def generate_stream(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model_name: Optional[str] = None,
    ):
        model = model_name or settings.GEMINI_MODEL

        contents = []
        for msg in messages:
            role = "user" if msg["role"] in ["user", "tool"] else "model"
            content_text = msg.get("content", "")
            if msg.get("role") == "tool":
                content_text = f"[Tool Output for {msg.get('name', 'tool')}]: {content_text}"
            contents.append(types.Content(
                role=role,
                parts=[types.Part.from_text(text=content_text)]
            ))

        gemini_tools = None
        if tools:
            declarations = []
            for t in tools:
                declarations.append(types.FunctionDeclaration(
                    name=t["name"],
                    description=t.get("description", ""),
                    parameters=t.get("parameters", {}),
                ))
            gemini_tools = [types.Tool(function_declarations=declarations)]

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=gemini_tools,
        )

        try:
            # Check if using the async client wrapper or sync wrapper
            # For simplicity, we'll use the sync streaming and wrap in an async generator
            import asyncio
            
            def _sync_generate():
                return self.client.models.generate_content_stream(
                    model=model,
                    contents=contents,
                    config=config,
                )
            
            response_stream = await asyncio.to_thread(_sync_generate)
            
            tool_calls = []
            for chunk in response_stream:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    for part in candidate.content.parts:
                        if part.function_call:
                            args = part.function_call.args
                            tool_calls.append(ToolCall(
                                id=f"call_{part.function_call.name}_{len(tool_calls)}",
                                name=part.function_call.name,
                                arguments=dict(args) if args else {},
                            ))
                        elif part.text:
                            yield part.text

            if tool_calls:
                yield {"type": "tool_calls", "calls": tool_calls}

        except Exception as e:
            logger.error(f"Gemini streaming error: {e}")
            raise
