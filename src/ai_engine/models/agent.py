"""
AI Engine Models — Agent (AI Agent Configuration).

Conversion du modèle Django `Agent` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/agent.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import AgentRole


class AgentConfig(BaseModel):
    """Configuration comportementale d'un agent.

    Remplace le JSONField `config` + champs individuels du modèle Django.
    """

    max_iterations: int = Field(
        default=10,
        ge=1,
        description="Nombre max d'itérations par exécution",
    )
    max_tokens_per_run: int = Field(
        default=8000,
        ge=1,
        description="Nombre max de tokens par exécution",
    )
    temperature: float | None = Field(
        default=None,
        ge=0.0,
        le=2.0,
        description="Override de la temperature du provider (None = utiliser celle du provider)",
    )
    max_tokens_per_response: int | None = Field(
        default=None,
        description="Override du max_tokens du provider",
    )
    enable_memory: bool = True
    enable_tools: bool = True
    enable_rag: bool = False
    retry_on_failure: bool = True
    max_retries: int = 3
    extra: dict[str, object] = Field(
        default_factory=dict,
        description="Configuration supplémentaire libre",
    )


class Agent(BaseModel):
    """
    Agent AI — acteur intelligent qui utilise un Provider LLM.

    Équivalent standalone du modèle Django `Agent`.

    Usage:
        agent = Agent(
            name="Research Assistant",
            slug="research-assistant",
            role=AgentRole.RESEARCHER,
            provider_id="provider-uuid",
            system_prompt="Tu es un chercheur expert...",
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    slug: str = ""
    description: str = ""

    # Rôle
    role: AgentRole = AgentRole.ASSISTANT

    # Provider LLM (référence par ID)
    provider_id: str = Field(
        ...,
        description="ID du LLMProviderConfig utilisé par cet agent",
    )

    # Model override (si différent du default_model du provider)
    model: str | None = Field(
        default=None,
        description="Override du modèle LLM (None = utiliser le default_model du provider)",
    )

    # Prompts
    system_prompt: str = Field(
        default="",
        description="Prompt système définissant le comportement de l'agent",
    )
    welcome_message: str = Field(
        default="",
        description="Message d'accueil (optionnel)",
    )

    # Configuration
    config: AgentConfig = Field(default_factory=AgentConfig)

    # Relations (références par ID — framework-agnostic)
    tool_ids: list[str] = Field(
        default_factory=list,
        description="IDs des ToolDefinition accessibles par cet agent",
    )
    skill_ids: list[str] = Field(
        default_factory=list,
        description="IDs des Skills de cet agent",
    )
    knowledge_base_ids: list[str] = Field(
        default_factory=list,
        description="IDs des KnowledgeSource accessibles",
    )

    # Ownership (framework-agnostic — remplace ForeignKey(User))
    owner_id: str | None = Field(
        default=None,
        description="ID du propriétaire (user_id, tenant_id, etc.)",
    )

    # État
    is_active: bool = True

    # Metadata
    metadata: dict[str, object] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get_effective_temperature(self) -> float | None:
        """Retourne la temperature effective (agent override ou None pour provider default)."""
        return self.config.temperature
