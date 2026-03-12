"""
AI Engine Models — Execution (Execution Tracking).

Conversion des modèles Django `Execution` + `ExecutionStep` en Pydantic BaseModel purs.
Remplace : django-ai-app/models/execution.py

Execution = une session complète d'exécution d'un agent.
ExecutionStep = chaque étape/action dans cette exécution.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.models.message import TokenUsage
from ai_engine.types import ExecutionStatus, StepType


class ExecutionStep(BaseModel):
    """
    Étape individuelle dans une Execution.

    Chaque appel LLM, appel de tool, ou décision est tracé ici.

    Équivalent standalone du modèle Django `ExecutionStep`.

    Usage:
        step = ExecutionStep(
            execution_id="exec-uuid",
            step_type=StepType.LLM_CALL,
            order=1,
            input_data={"prompt": "..."},
            output_data={"response": "..."},
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Execution parente (référence par ID — remplace ForeignKey)
    execution_id: str = Field(
        ...,
        description="ID de l'Execution parente",
    )

    # Type d'étape
    step_type: StepType

    # Ordre dans l'exécution
    order: int = Field(default=0, ge=0)

    # Données
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] = Field(default_factory=dict)
    error: str = ""

    # Tool utilisé (si step_type=TOOL_CALL — référence par ID)
    tool_id: str | None = Field(
        default=None,
        description="ID du ToolDefinition utilisé (si step_type=tool_call)",
    )

    # Métriques
    tokens_used: int = Field(default=0, ge=0)
    cost: float = Field(
        default=0.0,
        ge=0.0,
        description="Coût de cette étape en USD",
    )
    duration_ms: int = Field(
        default=0,
        ge=0,
        description="Durée en millisecondes",
    )

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Execution(BaseModel):
    """
    Session d'exécution d'un Agent.

    Trace une exécution complète : du prompt initial au résultat final.

    Équivalent standalone du modèle Django `Execution`.

    Usage:
        execution = Execution(
            agent_id="agent-uuid",
            input_data={"prompt": "Analyse ce document"},
        )
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(timezone.utc)
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Agent (référence par ID — remplace ForeignKey)
    agent_id: str = Field(
        ...,
        description="ID de l'Agent qui exécute",
    )

    # Graph utilisé (optionnel — référence par ID)
    graph_id: str | None = Field(
        default=None,
        description="ID du Graph utilisé (si exécution via graph)",
    )

    # Conversation liée (optionnel — référence par ID)
    conversation_id: str | None = Field(
        default=None,
        description="ID de la Conversation liée (si applicable)",
    )

    # Status
    status: ExecutionStatus = ExecutionStatus.PENDING

    # Input / Output
    input_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Données d'entrée de l'exécution",
    )
    output_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Résultat final de l'exécution",
    )
    error: str = ""

    # Métriques agrégées
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="Métriques de tokens agrégées pour toute l'exécution",
    )
    total_steps: int = Field(default=0, ge=0)

    # Timestamps
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Contexte / Metadata
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Métadonnées (user_id, source, trigger, etc.)",
    )

    @property
    def duration(self) -> timedelta | None:
        """Durée de l'exécution."""
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

    @property
    def duration_ms(self) -> int | None:
        """Durée de l'exécution en millisecondes."""
        d = self.duration
        if d is not None:
            return int(d.total_seconds() * 1000)
        return None

    @property
    def is_terminal(self) -> bool:
        """True si l'exécution est dans un état terminal."""
        return self.status in (
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        )
