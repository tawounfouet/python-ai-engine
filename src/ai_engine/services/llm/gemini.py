"""
Gemini LLM Client Implementation.

Implémentation du client pour l'API Google Gemini.
Implementation de base - peut être étendue avec les spécificités de Gemini.

Dépendances requises:
    pip install google-generativeai

Usage:
    provider = LLMProviderConfig(
        name="Google Gemini",
        provider_type=ProviderType.GEMINI,
        default_model="gemini-pro",
        api_key="...",
    )
    client = GeminiClient(provider)
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

try:
    import google.generativeai as genai
except ImportError as e:
    raise ImportError(
        "Gemini client requires 'google-generativeai' package. Install with: pip install google-generativeai"
    ) from e

from ai_engine.exceptions import LLMError
from ai_engine.models.message import Message
from ai_engine.services.llm.base import (
    LLMClient,
    LLMRequest,
    LLMResponse,
    StreamChunk,
    TokenUsage,
)
from ai_engine.types import MessageRole


class GeminiClient(LLMClient):
    """Client pour l'API Google Gemini."""

    def __init__(self, provider_config: Any) -> None:
        super().__init__(provider_config)

        api_key = provider_config.get_api_key_value()
        if not api_key:
            raise ValueError("Gemini API key is required")

        # Configuration
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(provider_config.default_model)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complétion synchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Convertir les messages
            prompt = self._prepare_prompt(request.messages)

            # Configuration
            generation_config = genai.types.GenerationConfig(
                temperature=request.temperature
                or self.provider_config.settings.temperature,
                max_output_tokens=request.max_tokens
                or self.provider_config.settings.max_tokens,
            )

            # Appel à l'API
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # Convertir la réponse
            return self._convert_response(response, start_time)

        except Exception as e:
            raise LLMError(f"Gemini API error: {e}") from e

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """Complétion asynchrone - utilise la version sync pour l'instant."""
        # Gemini n'a pas encore d'API async officielle dans tous les cas
        return self.complete(request)

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """Streaming synchrone."""
        self.validate_capabilities(request)

        try:
            prompt = self._prepare_prompt(request.messages)
            generation_config = genai.types.GenerationConfig(
                temperature=request.temperature
                or self.provider_config.settings.temperature,
                max_output_tokens=request.max_tokens
                or self.provider_config.settings.max_tokens,
            )

            response = self.model.generate_content(
                prompt,
                generation_config=generation_config,
                stream=True,
            )

            for chunk in response:
                if chunk.text:
                    yield StreamChunk(delta=chunk.text)

        except Exception as e:
            raise LLMError(f"Gemini API error: {e}") from e

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Streaming asynchrone - utilise la version sync pour l'instant."""
        for chunk in self.stream(request):
            yield chunk

    def _prepare_prompt(self, messages: list[Message]) -> str:
        """Convertit les messages en prompt pour Gemini."""
        # Simple conversion - peut être améliorée
        parts = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                parts.append(f"System: {msg.content}")
            elif msg.role == MessageRole.USER:
                parts.append(f"Human: {msg.content}")
            elif msg.role == MessageRole.ASSISTANT:
                parts.append(f"Assistant: {msg.content}")

        return "\n\n".join(parts)

    def _convert_response(self, response: Any, start_time: float) -> LLMResponse:
        """Convertit une réponse Gemini en LLMResponse."""
        content = response.text or ""

        # Usage (si disponible)
        usage = None
        if hasattr(response, "usage_metadata"):
            usage = TokenUsage(
                prompt_tokens=getattr(response.usage_metadata, "prompt_token_count", 0),
                completion_tokens=getattr(
                    response.usage_metadata, "candidates_token_count", 0
                ),
                total_tokens=getattr(response.usage_metadata, "total_token_count", 0),
            )

        return LLMResponse(
            content=content,
            model=self.provider_config.default_model,
            usage=usage,
            response_time_ms=(time.time() - start_time) * 1000,
        )
