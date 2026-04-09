"""
AI Engine — Event Definitions.

Modèles Pydantic pour tous les événements circulant dans l'EventBus.

Chaque événement hérite de BaseEvent et transporte des données typées
spécifiques à son contexte.

Usage:
    from ai_engine.events.events import ToolCalledEvent, MessageReceivedEvent

    event = ToolCalledEvent(
        tool_name="calculator",
        arguments={"expression": "2+2"},
        conversation_id="conv-123",
    )
    bus.emit(event)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import EventType


class BaseEvent(BaseModel):
    """Événement de base dont tous les événements héritent."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Contexte optionnel (agent, conversation, execution)
    agent_id: str | None = None
    conversation_id: str | None = None
    execution_id: str | None = None
    # Données libres supplémentaires
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"frozen": True}


# ──────────────────────────────────────────────
# Agent Events
# ──────────────────────────────────────────────


class AgentCreatedEvent(BaseEvent):
    """Émis quand un nouvel agent est créé."""

    event_type: EventType = EventType.AGENT_CREATED
    agent_name: str
    agent_role: str


class AgentUpdatedEvent(BaseEvent):
    """Émis quand un agent est mis à jour."""

    event_type: EventType = EventType.AGENT_UPDATED
    updated_fields: list[str] = Field(default_factory=list)


class AgentDeletedEvent(BaseEvent):
    """Émis quand un agent est supprimé."""

    event_type: EventType = EventType.AGENT_DELETED


# ──────────────────────────────────────────────
# Conversation Events
# ──────────────────────────────────────────────


class ConversationStartedEvent(BaseEvent):
    """Émis quand une conversation démarre."""

    event_type: EventType = EventType.CONVERSATION_STARTED
    title: str = ""


class ConversationEndedEvent(BaseEvent):
    """Émis quand une conversation se termine."""

    event_type: EventType = EventType.CONVERSATION_ENDED
    message_count: int = 0


# ──────────────────────────────────────────────
# Message Events
# ──────────────────────────────────────────────


class MessageSentEvent(BaseEvent):
    """Émis quand un message utilisateur est envoyé."""

    event_type: EventType = EventType.MESSAGE_SENT
    message_id: str
    content_preview: str = ""  # Premiers 200 chars max


class MessageReceivedEvent(BaseEvent):
    """Émis quand un message assistant est reçu."""

    event_type: EventType = EventType.MESSAGE_RECEIVED
    message_id: str
    model: str = ""
    content_preview: str = ""


# ──────────────────────────────────────────────
# Tool Events
# ──────────────────────────────────────────────


class ToolCalledEvent(BaseEvent):
    """Émis juste avant l'exécution d'un tool."""

    event_type: EventType = EventType.TOOL_CALLED
    tool_name: str
    tool_call_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolSucceededEvent(BaseEvent):
    """Émis après l'exécution réussie d'un tool."""

    event_type: EventType = EventType.TOOL_SUCCEEDED
    tool_name: str
    tool_call_id: str
    output_preview: str = ""
    duration_ms: float | None = None


class ToolFailedEvent(BaseEvent):
    """Émis après l'échec d'un tool."""

    event_type: EventType = EventType.TOOL_FAILED
    tool_name: str
    tool_call_id: str
    error: str
    duration_ms: float | None = None


# ──────────────────────────────────────────────
# LLM Events
# ──────────────────────────────────────────────


class LLMRequestStartedEvent(BaseEvent):
    """Émis au début d'un appel LLM."""

    event_type: EventType = EventType.LLM_REQUEST_STARTED
    provider_type: str
    model: str
    message_count: int = 0


class LLMRequestCompletedEvent(BaseEvent):
    """Émis à la fin d'un appel LLM réussi."""

    event_type: EventType = EventType.LLM_REQUEST_COMPLETED
    provider_type: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    duration_ms: float | None = None
    finish_reason: str | None = None


class LLMRequestFailedEvent(BaseEvent):
    """Émis si un appel LLM échoue."""

    event_type: EventType = EventType.LLM_REQUEST_FAILED
    provider_type: str
    model: str
    error: str
    duration_ms: float | None = None


# ──────────────────────────────────────────────
# Skill Events
# ──────────────────────────────────────────────


class SkillStartedEvent(BaseEvent):
    """Émis au démarrage d'un skill."""

    event_type: EventType = EventType.SKILL_STARTED
    skill_key: str
    skill_name: str = ""


class SkillCompletedEvent(BaseEvent):
    """Émis à la fin d'un skill réussi."""

    event_type: EventType = EventType.SKILL_COMPLETED
    skill_key: str
    duration_ms: float | None = None


class SkillFailedEvent(BaseEvent):
    """Émis si un skill échoue."""

    event_type: EventType = EventType.SKILL_FAILED
    skill_key: str
    error: str
    duration_ms: float | None = None


# ──────────────────────────────────────────────
# Execution Events
# ──────────────────────────────────────────────


class ExecutionStartedEvent(BaseEvent):
    """Émis au démarrage d'une exécution."""

    event_type: EventType = EventType.EXECUTION_STARTED


class ExecutionCompletedEvent(BaseEvent):
    """Émis à la fin d'une exécution réussie."""

    event_type: EventType = EventType.EXECUTION_COMPLETED
    duration_ms: float | None = None
    total_tokens: int = 0


class ExecutionFailedEvent(BaseEvent):
    """Émis si une exécution échoue."""

    event_type: EventType = EventType.EXECUTION_FAILED
    error: str
    duration_ms: float | None = None


# ──────────────────────────────────────────────
# Custom Event
# ──────────────────────────────────────────────


class CustomEvent(BaseEvent):
    """Événement personnalisé libre."""

    event_type: EventType = EventType.CUSTOM
    name: str
    data: dict[str, Any] = Field(default_factory=dict)
