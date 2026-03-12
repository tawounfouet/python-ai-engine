"""
Base classes for LLM clients.

Définit l'interface abstraite commune à tous les providers LLM,
ainsi que les modèles de données pour les requêtes/réponses.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any, AsyncIterator, Iterator
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.models.message import Message
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.types import MessageRole


class TokenUsage(BaseModel):
    """Statistics d'utilisation des tokens."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ToolCall(BaseModel):
    """Représente un appel d'outil dans une réponse LLM."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    function_name: str
    arguments: dict[str, Any]


class LLMRequest(BaseModel):
    """Requête vers un LLM."""

    messages: list[Message]
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None

    # Advanced options
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: list[str] | None = None


class LLMResponse(BaseModel):
    """Réponse d'un LLM."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    content: str
    role: MessageRole = MessageRole.ASSISTANT
    model: str

    # Metadata
    finish_reason: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: TokenUsage | None = None

    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    response_time_ms: float | None = None

    def to_message(self) -> Message:
        """Convertit la réponse LLM en Message."""
        return Message(
            content=self.content,
            role=self.role,
            metadata={
                "llm_response_id": self.id,
                "model": self.model,
                "finish_reason": self.finish_reason,
                "usage": self.usage.model_dump() if self.usage else None,
                "response_time_ms": self.response_time_ms,
            },
        )


class StreamChunk(BaseModel):
    """Chunk de données streamées."""

    delta: str = ""
    finish_reason: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class LLMClient(ABC):
    """Interface abstraite pour tous les clients LLM."""

    def __init__(self, provider_config: LLMProviderConfig) -> None:
        self.provider_config = provider_config

    @abstractmethod
    def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Effectue une complétion synchrone.

        Args:
            request: La requête LLM

        Returns:
            La réponse du LLM

        Raises:
            LLMError: En cas d'erreur lors de la requête
        """
        pass

    @abstractmethod
    async def acomplete(self, request: LLMRequest) -> LLMResponse:
        """
        Effectue une complétion asynchrone.

        Args:
            request: La requête LLM

        Returns:
            La réponse du LLM

        Raises:
            LLMError: En cas d'erreur lors de la requête
        """
        pass

    @abstractmethod
    def stream(self, request: LLMRequest) -> Iterator[StreamChunk]:
        """
        Effectue une complétion avec streaming synchrone.

        Args:
            request: La requête LLM (request.stream sera forcé à True)

        Yields:
            Les chunks de la réponse streamée

        Raises:
            LLMError: En cas d'erreur lors de la requête
        """
        pass

    @abstractmethod
    async def astream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """
        Effectue une complétion avec streaming asynchrone.

        Args:
            request: La requête LLM (request.stream sera forcé à True)

        Yields:
            Les chunks de la réponse streamée

        Raises:
            LLMError: En cas d'erreur lors de la requête
        """
        pass

    def get_model(self) -> str:
        """Retourne le nom du modèle par défaut."""
        return self.provider_config.default_model

    def get_base_config(self) -> dict[str, Any]:
        """Retourne la configuration de base du provider."""
        settings = self.provider_config.settings
        return {
            "model": self.get_model(),
            "temperature": settings.temperature,
            "max_tokens": settings.max_tokens,
            "top_p": settings.top_p,
            "frequency_penalty": settings.frequency_penalty,
            "presence_penalty": settings.presence_penalty,
        }

    def validate_capabilities(self, request: LLMRequest) -> None:
        """
        Valide que la requête est compatible avec les capacités du provider.

        Raises:
            ValueError: Si la requête n'est pas supportée
        """
        capabilities = self.provider_config.capabilities

        if request.stream and not capabilities.streaming:
            raise ValueError(
                f"Streaming not supported by provider {self.provider_config.name}"
            )

        if request.tools and not capabilities.function_calling:
            raise ValueError(
                f"Function calling not supported by provider {self.provider_config.name}"
            )

        # Vérifier si des messages contiennent des images (vision)
        has_images = any(
            msg.metadata and msg.metadata.get("has_images", False)
            for msg in request.messages
        )
        if has_images and not capabilities.vision:
            raise ValueError(
                f"Vision not supported by provider {self.provider_config.name}"
            )

    # Convenience methods pour usage simple
    def chat(
        self,
        messages: list[Message] | str,
        model: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """
        Interface simplifiée pour une conversation.

        Args:
            messages: Liste de messages ou string simple (sera converti en user message)
            model: Override du modèle
            temperature: Override de la température
            **kwargs: Autres paramètres pour LLMRequest

        Returns:
            La réponse du LLM
        """
        if isinstance(messages, str):
            messages = [Message(content=messages, role=MessageRole.USER)]

        request = LLMRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            **kwargs,
        )
        return self.complete(request)

    async def achat(
        self,
        messages: list[Message] | str,
        model: str | None = None,
        temperature: float | None = None,
        **kwargs: Any,
    ) -> LLMResponse:
        """Version asynchrone de chat()."""
        if isinstance(messages, str):
            messages = [Message(content=messages, role=MessageRole.USER)]

        request = LLMRequest(
            messages=messages,
            model=model,
            temperature=temperature,
            **kwargs,
        )
        return await self.acomplete(request)

    def __enter__(self) -> LLMClient:
        """Support du context manager."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cleanup lors de la sortie du context manager."""
        pass
