"""
Anthropic LLM Client Implementation.

Implémentation du client pour l'API Anthropic (Claude).
Supporte les complétions synchrones/asynchrones et le streaming.

Dépendances requises:
    pip install anthropic

Usage:
    provider = LLMProviderConfig(
        name="Anthropic Claude",
        provider_type=ProviderType.ANTHROPIC,
        default_model="claude-3-opus-20240229",
        api_key="sk-ant-...",
    )
    client = AnthropicClient(provider)
    response = client.chat("Hello!")
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

try:
    import anthropic
    from anthropic import Anthropic, AsyncAnthropic
    from anthropic.types import Message as AnthropicMessage
except ImportError as e:
    raise ImportError(
        "Anthropic client requires 'anthropic' package. Install with: pip install anthropic"
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


class AnthropicClient(LLMClient):
    """Client pour l'API Anthropic."""

    def __init__(self, provider_config: Any) -> None:
        super().__init__(provider_config)

        api_key = provider_config.get_api_key_value()
        if not api_key:
            raise ValueError("Anthropic API key is required")

        # Configuration du client
        client_config = {
            "api_key": api_key,
            "timeout": provider_config.settings.timeout,
            "max_retries": provider_config.settings.max_retries,
        }

        if provider_config.api_base_url:
            client_config["base_url"] = provider_config.api_base_url

        self._sync_client = Anthropic(**client_config)
        self._async_client = AsyncAnthropic(**client_config)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complétion synchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer la requête Anthropic
            anthropic_request = self._prepare_request(request)

            # Appel à l'API
            completion = self._sync_client.messages.create(**anthropic_request)

            # Convertir la réponse
            response = self._convert_response(completion, start_time)
            return response

        except anthropic.AnthropicError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in Anthropic client: {e}") from e

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """Complétion asynchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer la requête Anthropic
            anthropic_request = self._prepare_request(request)

            # Appel à l'API
            completion = await self._async_client.messages.create(**anthropic_request)

            # Convertir la réponse
            response = self._convert_response(completion, start_time)
            return response

        except anthropic.AnthropicError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in Anthropic client: {e}") from e

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """Streaming synchrone."""
        self.validate_capabilities(request)

        try:
            # Préparer la requête avec stream=True
            anthropic_request = self._prepare_request(request)

            # Appel streaming à l'API
            with self._sync_client.messages.stream(**anthropic_request) as stream:
                for event in stream:
                    chunk = self._convert_stream_event(event)
                    if chunk:
                        yield chunk

        except anthropic.AnthropicError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in Anthropic client: {e}") from e

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Streaming asynchrone."""
        self.validate_capabilities(request)

        try:
            # Préparer la requête avec stream=True
            anthropic_request = self._prepare_request(request)

            # Appel streaming à l'API
            async with self._async_client.messages.stream(
                **anthropic_request
            ) as stream:
                async for event in stream:
                    chunk = self._convert_stream_event(event)
                    if chunk:
                        yield chunk

        except anthropic.AnthropicError as e:
            raise LLMError(f"Anthropic API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in Anthropic client: {e}") from e

    def _prepare_request(self, request: LLMRequest) -> dict[str, Any]:
        """Prépare la requête dans le format Anthropic."""
        base_config = self.get_base_config()

        # Séparer le system message des autres
        system_message = None
        messages = []

        for msg in request.messages:
            if msg.role == MessageRole.SYSTEM:
                system_message = msg.content
            else:
                messages.append(self._message_to_anthropic(msg))

        # Configuration de base
        anthropic_request = {
            "model": request.model or base_config["model"],
            "messages": messages,
            "temperature": request.temperature or base_config["temperature"],
        }

        if system_message:
            anthropic_request["system"] = system_message

        # Paramètres optionnels
        if request.max_tokens or base_config["max_tokens"]:
            anthropic_request["max_tokens"] = (
                request.max_tokens or base_config["max_tokens"]
            )
        else:
            # Anthropic exige max_tokens
            anthropic_request["max_tokens"] = 4096

        if request.top_p or base_config["top_p"]:
            anthropic_request["top_p"] = request.top_p or base_config["top_p"]

        if request.stop:
            anthropic_request["stop_sequences"] = request.stop

        # Function calling (tools)
        if request.tools:
            anthropic_request["tools"] = request.tools
            if request.tool_choice:
                anthropic_request["tool_choice"] = request.tool_choice

        return anthropic_request

    def _message_to_anthropic(self, message: Message) -> dict[str, Any]:
        """Convertit un Message en format Anthropic."""
        # Anthropic utilise 'user' et 'assistant' seulement
        role_mapping = {
            MessageRole.USER: "user",
            MessageRole.ASSISTANT: "assistant",
            MessageRole.TOOL: "user",  # Les résultats d'outils sont des messages user
        }

        return {
            "role": role_mapping.get(message.role, "user"),
            "content": message.content,
        }

    def _convert_response(
        self, completion: AnthropicMessage, start_time: float
    ) -> LLMResponse:
        """Convertit une réponse Anthropic en LLMResponse."""
        # Contenu (Anthropic peut avoir plusieurs content blocks)
        content = ""
        tool_calls = []

        for block in completion.content:
            if hasattr(block, "text"):
                content += block.text
            elif hasattr(block, "name"):  # Tool use block
                tool_calls.append(
                    ToolCall(
                        id=getattr(block, "id", ""),
                        function_name=block.name,
                        arguments=getattr(block, "input", {}),
                    )
                )

        # Usage
        usage = None
        if completion.usage:
            usage = TokenUsage(
                prompt_tokens=completion.usage.input_tokens,
                completion_tokens=completion.usage.output_tokens,
                total_tokens=completion.usage.input_tokens
                + completion.usage.output_tokens,
            )

        return LLMResponse(
            id=completion.id,
            content=content,
            model=completion.model,
            finish_reason=completion.stop_reason,
            tool_calls=tool_calls,
            usage=usage,
            response_time_ms=(time.time() - start_time) * 1000,
        )

    def _convert_stream_event(self, event: Any) -> StreamChunk | None:
        """Convertit un événement de stream Anthropic en StreamChunk."""
        # Anthropic utilise différents types d'événements
        if hasattr(event, "type"):
            if event.type == "content_block_delta":
                if hasattr(event.delta, "text"):
                    return StreamChunk(delta=event.delta.text)
            elif event.type == "message_stop":
                return StreamChunk(finish_reason="stop")

        return None
