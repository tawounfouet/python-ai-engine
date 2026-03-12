"""
AI Engine Models — Memory (Agent Persistent Memory).

Conversion du modèle Django `AgentMemory` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/memory.py

Permet aux agents de mémoriser des informations entre les exécutions :
  - SHORT_TERM : contexte de la session courante
  - LONG_TERM : connaissances acquises
  - EPISODIC : souvenirs d'exécutions passées
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import MemoryType


class AgentMemory(BaseModel):
    """
    Mémoire persistante d'un Agent.

    Équivalent standalone du modèle Django `AgentMemory`.

    Usage:
        memory = AgentMemory(
            agent_id="agent-uuid",
            key="user_preferences",
            content='{"language": "fr", "tone": "formal"}',
            memory_type=MemoryType.LONG_TERM,
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Agent (référence par ID — remplace ForeignKey)
    agent_id: str = Field(
        ...,
        description="ID de l'Agent propriétaire de cette mémoire",
    )

    # Type de mémoire
    memory_type: MemoryType = MemoryType.LONG_TERM

    # Clé unique pour retrouver la mémoire
    key: str = Field(
        ...,
        description="Clé de la mémoire (ex: user_preferences, last_research)",
    )

    # Contenu
    content: str = Field(
        ...,
        description="Contenu mémorisé (texte brut ou JSON sérialisé)",
    )

    # Embedding pour recherche sémantique (optionnel)
    embedding: list[float] | None = Field(
        default=None,
        description="Vecteur d'embedding pour recherche sémantique",
    )

    # Score de pertinence (décroît avec le temps pour short_term)
    relevance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Score de pertinence (0.0 à 1.0)",
    )

    # Métadonnées
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Expiration (pour short_term)
    expires_at: datetime | None = Field(
        default=None,
        description="Date d'expiration (pour mémoire court terme)",
    )

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_expired(self) -> bool:
        """True si la mémoire a expiré."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) >= self.expires_at
