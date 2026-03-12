"""
Ollama LLM Client Implementation.

Implémentation du client pour Ollama (modèles locaux).
Supporte les modèles hébergés localement via Ollama.

Dépendances requises:
    pip install ollama

Usage:
    provider = LLMProviderConfig(
        name="Ollama Local",
        provider_type=ProviderType.OLLAMA,
        default_model="llama3",
        api_base_url="http://localhost:11434",
    )
    client = OllamaClient(provider)
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

try:
    import ollama
except ImportError as e:
    raise ImportError(
        "Ollama client requires 'ollama' package. Install with: pip install ollama"
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


class OllamaClient(LLMClient):
    """Client pour Ollama."""

    def __init__(self, provider_config: Any) -> None:
        super().__init__(provider_config)

        # Configuration du client Ollama
        self.base_url = provider_config.api_base_url or "http://localhost:11434"
        self.client = ollama.Client(host=self.base_url)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complétion synchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer les messages
            messages = [self._message_to_ollama(msg) for msg in request.messages]

            # Options
            options = {}
            if request.temperature is not None:
                options["temperature"] = request.temperature
            elif self.provider_config.settings.temperature is not None:
                options["temperature"] = self.provider_config.settings.temperature

            # Appel à l'API
            response = self.client.chat(
                model=request.model or self.provider_config.default_model,
                messages=messages,
                options=options,
            )

            # Convertir la réponse
            return self._convert_response(response, start_time)

        except Exception as e:
            raise LLMError(f"Ollama API error: {e}") from e

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """Complétion asynchrone."""
        # Ollama supporte async dans certaines versions
        try:
            start_time = time.time()
            messages = [self._message_to_ollama(msg) for msg in request.messages]

            options = {}
            if request.temperature is not None:
                options["temperature"] = request.temperature

            # Tentative d'appel async
            async_client = ollama.AsyncClient(host=self.base_url)
            response = await async_client.chat(
                model=request.model or self.provider_config.default_model,
                messages=messages,
                options=options,
            )

            return self._convert_response(response, start_time)

        except Exception as e:
            # Fallback sur la version sync
            return self.complete(request)

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """Streaming synchrone."""
        self.validate_capabilities(request)

        try:
            messages = [self._message_to_ollama(msg) for msg in request.messages]

            options = {}
            if request.temperature is not None:
                options["temperature"] = request.temperature

            # Streaming
            stream = self.client.chat(
                model=request.model or self.provider_config.default_model,
                messages=messages,
                options=options,
                stream=True,
            )

            for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield StreamChunk(delta=chunk["message"]["content"])

        except Exception as e:
            raise LLMError(f"Ollama API error: {e}") from e

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Streaming asynchrone."""
        try:
            messages = [self._message_to_ollama(msg) for msg in request.messages]

            options = {}
            if request.temperature is not None:
                options["temperature"] = request.temperature

            async_client = ollama.AsyncClient(host=self.base_url)
            stream = await async_client.chat(
                model=request.model or self.provider_config.default_model,
                messages=messages,
                options=options,
                stream=True,
            )

            async for chunk in stream:
                if "message" in chunk and "content" in chunk["message"]:
                    yield StreamChunk(delta=chunk["message"]["content"])

        except Exception as e:
            # Fallback sur sync
            for chunk in self.stream(request):
                yield chunk

    def _message_to_ollama(self, message: Message) -> dict[str, Any]:
        """Convertit un Message en format Ollama."""
        role_mapping = {
            MessageRole.SYSTEM: "system",
            MessageRole.USER: "user",
            MessageRole.ASSISTANT: "assistant",
        }

        return {
            "role": role_mapping.get(message.role, "user"),
            "content": message.content,
        }

    def _convert_response(
        self, response: dict[str, Any], start_time: float
    ) -> LLMResponse:
        """Convertit une réponse Ollama en LLMResponse."""
        message = response.get("message", {})
        content = message.get("content", "")

        # Usage (si disponible dans les métadonnées)
        usage = None
        if "eval_count" in response and "prompt_eval_count" in response:
            usage = TokenUsage(
                prompt_tokens=response["prompt_eval_count"],
                completion_tokens=response["eval_count"],
                total_tokens=response["prompt_eval_count"] + response["eval_count"],
            )

        return LLMResponse(
            content=content,
            model=response.get("model", self.provider_config.default_model),
            usage=usage,
            response_time_ms=(time.time() - start_time) * 1000,
        )
