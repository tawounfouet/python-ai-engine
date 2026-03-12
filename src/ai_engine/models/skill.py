"""
AI Engine Models — Skill (High-Level Agent Capabilities).

Conversion des modèles Django `Skill` + `AgentSkill` en Pydantic BaseModel purs.
Remplace : django-ai-app/models/skill.py

Skill vs Tool:
  - Tool = Fonction technique atomique (API call, DB query)
  - Skill = Capacité combinant plusieurs tools + raisonnement

Exemples:
  - ResearchSkill = web_search + summarize + fact_check
  - CodingSkill = generate_code + run_tests + code_review
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import Proficiency, SkillCategory


class Skill(BaseModel):
    """
    Capacité de haut niveau pour un Agent.

    Un Skill combine plusieurs Tools avec un prompt système
    pour accomplir une tâche complexe.

    Équivalent standalone du modèle Django `Skill`.

    Usage:
        skill = Skill(
            key="research",
            name="Research Skill",
            category=SkillCategory.RESEARCH,
            system_prompt="Tu es un chercheur expert...",
            required_tool_ids=["web_search_id", "summarize_id"],
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    key: str = Field(
        ...,
        description="Identifiant unique du skill (ex: research, coding)",
    )
    name: str
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM

    # Prompt système pour ce skill
    system_prompt: str = Field(
        default="",
        description="Instructions système pour ce skill",
    )

    # Tools requis (références par ID — remplace ManyToManyField)
    required_tool_ids: list[str] = Field(
        default_factory=list,
        description="IDs des ToolDefinition nécessaires pour ce skill",
    )

    # Configuration
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration du skill (paramètres, limites, etc.)",
    )

    # Provider recommandé (référence par ID — remplace ForeignKey)
    recommended_provider_id: str | None = Field(
        default=None,
        description="ID du LLMProviderConfig recommandé pour ce skill",
    )

    # État
    is_active: bool = True

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentSkillAssignment(BaseModel):
    """
    Association Agent-Skill avec configuration.

    Équivalent standalone du modèle Django `AgentSkill` (table through).

    Usage:
        assignment = AgentSkillAssignment(
            agent_id="agent-uuid",
            skill_id="skill-uuid",
            proficiency=Proficiency.ADVANCED,
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Relations (références par ID)
    agent_id: str = Field(
        ...,
        description="ID de l'Agent",
    )
    skill_id: str = Field(
        ...,
        description="ID du Skill",
    )

    # Override du provider pour cet agent (référence par ID)
    provider_override_id: str | None = Field(
        default=None,
        description="ID du LLMProviderConfig override pour cet agent",
    )

    # Niveau de maîtrise
    proficiency: Proficiency = Proficiency.INTERMEDIATE

    # État
    enabled: bool = True

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
