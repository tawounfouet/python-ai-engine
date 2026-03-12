"""
OpenAI LLM Client Implementation.

Implémentation du client pour l'API OpenAI (ChatGPT, GPT-4, etc.).
Supporte les complétions synchrones/asynchrones et le streaming.

Dépendances requises:
    pip install openai

Usage:
    provider = LLMProviderConfig(
        name="OpenAI GPT-4",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key="sk-...",
    )
    client = OpenAIClient(provider)
    response = client.chat("Hello!")
"""

from __future__ import annotations

import time
from typing import Any, AsyncIterator, Iterator

try:
    import openai
    from openai import OpenAI, AsyncOpenAI
    from openai.types.chat import ChatCompletion, ChatCompletionChunk
    from openai.types.chat.chat_completion import Choice
    from openai.types.chat.chat_completion_chunk import ChoiceDelta
except ImportError as e:
    raise ImportError(
        "OpenAI client requires 'openai' package. Install with: pip install openai"
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


class OpenAIClient(LLMClient):
    """Client pour l'API OpenAI."""

    def __init__(self, provider_config: Any) -> None:
        super().__init__(provider_config)

        api_key = provider_config.get_api_key_value()
        if not api_key:
            raise ValueError("OpenAI API key is required")

        # Configuration du client
        client_config = {
            "api_key": api_key,
            "timeout": provider_config.settings.timeout,
            "max_retries": provider_config.settings.max_retries,
        }

        # Support pour API base URL custom (ex: Azure OpenAI)
        if provider_config.api_base_url:
            client_config["base_url"] = provider_config.api_base_url

        self._sync_client = OpenAI(**client_config)
        self._async_client = AsyncOpenAI(**client_config)

    def complete(self, request: LLMRequest) -> LLMResponse:
        """Complétion synchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer la requête OpenAI
            openai_request = self._prepare_request(request)

            # Appel à l'API
            completion = self._sync_client.chat.completions.create(**openai_request)

            # Convertir la réponse
            response = self._convert_response(completion, start_time)
            return response

        except openai.OpenAIError as e:
            raise LLMError(f"OpenAI API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in OpenAI client: {e}") from e

    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """Complétion asynchrone."""
        self.validate_capabilities(request)

        start_time = time.time()
        try:
            # Préparer la requête OpenAI
            openai_request = self._prepare_request(request)

            # Appel à l'API
            completion = await self._async_client.chat.completions.create(
                **openai_request
            )

            # Convertir la réponse
            response = self._convert_response(completion, start_time)
            return response

        except openai.OpenAIError as e:
            raise LLMError(f"OpenAI API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in OpenAI client: {e}") from e

    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """Streaming synchrone."""
        self.validate_capabilities(request)

        try:
            # Préparer la requête avec stream=True
            openai_request = self._prepare_request(request)
            openai_request["stream"] = True

            # Appel streaming à l'API
            stream = self._sync_client.chat.completions.create(**openai_request)

            # Yield les chunks convertis
            for chunk in stream:
                yield self._convert_stream_chunk(chunk)

        except openai.OpenAIError as e:
            raise LLMError(f"OpenAI API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in OpenAI client: {e}") from e

    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Streaming asynchrone."""
        self.validate_capabilities(request)

        try:
            # Préparer la requête avec stream=True
            openai_request = self._prepare_request(request)
            openai_request["stream"] = True

            # Appel streaming à l'API
            stream = await self._async_client.chat.completions.create(**openai_request)

            # Yield les chunks convertis
            async for chunk in stream:
                yield self._convert_stream_chunk(chunk)

        except openai.OpenAIError as e:
            raise LLMError(f"OpenAI API error: {e}") from e
        except Exception as e:
            raise LLMError(f"Unexpected error in OpenAI client: {e}") from e

    def _prepare_request(self, request: LLMRequest) -> dict[str, Any]:
        """Prépare la requête dans le format OpenAI."""
        base_config = self.get_base_config()

        # Messages au format OpenAI
        messages = [self._message_to_openai(msg) for msg in request.messages]

        # Configuration de base
        openai_request = {
            "model": request.model or base_config["model"],
            "messages": messages,
            "temperature": request.temperature or base_config["temperature"],
        }

        # Paramètres optionnels
        if request.max_tokens or base_config["max_tokens"]:
            openai_request["max_tokens"] = (
                request.max_tokens or base_config["max_tokens"]
            )

        if request.top_p or base_config["top_p"]:
            openai_request["top_p"] = request.top_p or base_config["top_p"]

        if request.frequency_penalty or base_config["frequency_penalty"]:
            openai_request["frequency_penalty"] = (
                request.frequency_penalty or base_config["frequency_penalty"]
            )

        if request.presence_penalty or base_config["presence_penalty"]:
            openai_request["presence_penalty"] = (
                request.presence_penalty or base_config["presence_penalty"]
            )

        if request.stop:
            openai_request["stop"] = request.stop

        # Function calling
        if request.tools:
            openai_request["tools"] = request.tools
            if request.tool_choice:
                openai_request["tool_choice"] = request.tool_choice

        return openai_request

    def _message_to_openai(self, message: Message) -> dict[str, Any]:
        """Convertit un Message en format OpenAI."""
        openai_msg = {
            "role": message.role.value,
            "content": message.content,
        }

        # Support des tool calls dans les messages assistant
        if message.role == MessageRole.ASSISTANT and message.metadata:
            tool_calls = message.metadata.get("tool_calls")
            if tool_calls:
                openai_msg["tool_calls"] = tool_calls

        # Support des tool results
        if message.role == MessageRole.TOOL and message.metadata:
            tool_call_id = message.metadata.get("tool_call_id")
            if tool_call_id:
                openai_msg["tool_call_id"] = tool_call_id

        return openai_msg

    def _convert_response(
        self, completion: ChatCompletion, start_time: float
    ) -> LLMResponse:
        """Convertit une réponse OpenAI en LLMResponse."""
        choice = completion.choices[0]
        message = choice.message

        # Tool calls
        tool_calls = []
        if message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function_name=tc.function.name,
                    arguments=tc.function.arguments,  # Déjà un dict en OpenAI v1+
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

    def _convert_stream_chunk(self, chunk: ChatCompletionChunk) -> StreamChunk:
        """Convertit un chunk de stream OpenAI en StreamChunk."""
        if not chunk.choices:
            return StreamChunk()

        choice = chunk.choices[0]
        delta = choice.delta

        # Contenu
        content = delta.content or ""

        # Tool calls (dans les chunks)
        tool_calls = []
        if delta.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id or "",
                    function_name=tc.function.name or "" if tc.function else "",
                    arguments=tc.function.arguments or {} if tc.function else {},
                )
                for tc in delta.tool_calls
                if tc.function
            ]

        return StreamChunk(
            delta=content,
            finish_reason=choice.finish_reason,
            tool_calls=tool_calls,
        )
