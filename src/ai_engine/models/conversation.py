"""
AI Engine Models — Conversation (Chat Session).

Modèle nouveau — n'existe pas directement dans le Django app.
Dans Django, la conversation était implicitement gérée via Execution.
Ici on sépare le concept de "session de chat" de celui d'"exécution technique".

Conversation = session de chat entre un utilisateur et un agent.
Execution = exécution technique d'un agent (peut être liée à une conversation).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import ConversationStatus


class Conversation(BaseModel):
    """
    Session de conversation entre un utilisateur et un Agent.

    Usage:
        conversation = Conversation(
            title="Research on quantum computing",
            agent_id="agent-uuid",
            owner_id="user-123",
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str = Field(
        default="",
        description="Titre de la conversation (auto-généré ou défini par l'utilisateur)",
    )

    # Relations (références par ID)
    agent_id: str = Field(
        ...,
        description="ID de l'Agent participant à la conversation",
    )

    # Ownership (framework-agnostic)
    owner_id: str | None = Field(
        default=None,
        description="ID du propriétaire (user_id, tenant_id, etc.)",
    )

    # Status
    status: ConversationStatus = ConversationStatus.ACTIVE

    # Contexte de la conversation
    summary: str = Field(
        default="",
        description="Résumé courant de la conversation (pour le contexte long-terme)",
    )

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Compteurs (dénormalisés pour performance)
    message_count: int = Field(
        default=0,
        ge=0,
        description="Nombre de messages dans la conversation",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total de tokens utilisés dans la conversation",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_message_at: datetime | None = Field(
        default=None,
        description="Timestamp du dernier message",
    )
