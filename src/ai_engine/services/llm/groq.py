"""
Groq LLM Client Implementation.

Implémentation du client pour l'API Groq (modèles ultra-rapides).
Utilise une interface compatible OpenAI.

Dépendances requises:
    pip install groq

Usage:
    provider = LLMProviderConfig(
        name="Groq LLama",
        provider_type=ProviderType.GROQ,
        default_model="llama-3.1-405b-reasoning",
        api_key="gsk_...",
    )
    client = GroqClient(provider)
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

try:
    from groq import Groq, AsyncGroq
except ImportError as e:
    raise ImportError(
        "Groq client requires 'groq' package. Install with: pip install groq"
    ) from e

from ai_engine.exceptions import LLMError
from ai_engine.models.message import Message
from ai_engine.services.llm.base import (
    LLMClient,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    TokenUsage,
    ToolCall,
)
from ai_engine.types import MessageRole


class GroqClient(LLMClient):
    """Client pour l'API Groq."""

    def __init__(self, provider_config: Any) -> None:
        super().__init__(provider_config)

        api_key = provider_config.get_api_key_value()
        if not api_key:
            raise ValueError("Groq API key is required")

        # Configuration du client (API compatible OpenAI)
        self.client = Groq(api_key=api_key)
        self.async_client = AsyncGroq(api_key=api_key)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complétion synchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer la requête (format OpenAI)
            groq_request = self._prepare_request(request)

            # Appel à l'API
            completion = self.client.chat.completions.create(**groq_request)

            # Convertir la réponse
            return self._convert_response(completion, start_time)

        except Exception as e:
            raise LLMError(f"Groq API error: {e}") from e

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """Complétion asynchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            groq_request = self._prepare_request(request)
            completion = await self.async_client.chat.completions.create(**groq_request)
            return self._convert_response(completion, start_time)

        except Exception as e:
            raise LLMError(f"Groq API error: {e}") from e

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """Streaming synchrone."""
        self.validate_capabilities(request)

        try:
            groq_request = self._prepare_request(request)
            groq_request["stream"] = True

            stream = self.client.chat.completions.create(**groq_request)

            for chunk in stream:
                yield self._convert_stream_chunk(chunk)

        except Exception as e:
            raise LLMError(f"Groq API error: {e}") from e

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Streaming asynchrone."""
        self.validate_capabilities(request)

        try:
            groq_request = self._prepare_request(request)
            groq_request["stream"] = True

            stream = await self.async_client.chat.completions.create(**groq_request)

            async for chunk in stream:
                yield self._convert_stream_chunk(chunk)

        except Exception as e:
            raise LLMError(f"Groq API error: {e}") from e

    def _prepare_request(self, request: LLMRequest) -> dict[str, Any]:
        """Prépare la requête dans le format Groq (compatible OpenAI)."""
        base_config = self.get_base_config()

        # Messages au format OpenAI
        messages = [self._message_to_groq(msg) for msg in request.messages]

        # Configuration
        groq_request = {
            "model": request.model or base_config["model"],
            "messages": messages,
            "temperature": request.temperature or base_config["temperature"],
        }

        # Paramètres optionnels
        if request.max_tokens or base_config["max_tokens"]:
            groq_request["max_tokens"] = request.max_tokens or base_config["max_tokens"]

        if request.top_p or base_config["top_p"]:
            groq_request["top_p"] = request.top_p or base_config["top_p"]

        if request.stop:
            groq_request["stop"] = request.stop

        # Function calling (si supporté par le modèle)
        if request.tools:
            groq_request["tools"] = request.tools
            if request.tool_choice:
                groq_request["tool_choice"] = request.tool_choice

        return groq_request

    def _message_to_groq(self, message: Message) -> dict[str, Any]:
        """Convertit un Message en format Groq."""
        return {
            "role": message.role.value,
            "content": message.content,
        }

    def _convert_response(self, completion: Any, start_time: float) -> LLMResponse:
        """Convertit une réponse Groq en LLMResponse."""
        choice = completion.choices[0]
        message = choice.message

        # Tool calls
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function_name=tc.function.name,
                    arguments=tc.function.arguments,
                )
                for tc in message.tool_calls
            ]

        # Usage
        usage = None
        if completion.usage:
            usage = TokenUsage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
            )

        return LLMResponse(
            id=completion.id,
            content=message.content or "",
            model=completion.model,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
            usage=usage,
            response_time_ms=(time.time() - start_time) * 1000,
        )

    def _convert_stream_chunk(self, chunk: Any) -> StreamChunk:
        """Convertit un chunk de stream Groq en StreamChunk."""
        if not chunk.choices:
            return StreamChunk()

        choice = chunk.choices[0]
        delta = choice.delta

        content = delta.content or ""

        return StreamChunk(
            delta=content,
            finish_reason=choice.finish_reason,
        )
