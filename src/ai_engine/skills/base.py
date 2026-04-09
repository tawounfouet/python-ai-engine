"""
AI Engine — BaseSkill ABC.

Classe de base abstraite pour implémenter des Skills concrets.

Un Skill est une capacité de haut niveau qui :
  - Combine plusieurs tools + un LLM pour accomplir une tâche complexe
  - Peut être assigné à des agents
  - Émet des événements via l'EventBus (optionnel)

Différence Tool vs Skill :
  - Tool  = fonction atomique (calcul, requête HTTP, recherche web)
  - Skill = orchestration de tools + raisonnement LLM (ex: ResearchSkill)

Usage:
    class SummarizeSkill(BaseSkill):
        key = "summarize"
        name = "Summarize Text"
        description = "Summarizes a long text into key bullet points."
        required_tool_keys = []  # Pas de tools requis pour ce skill

        def run(self, text: str, *, llm_client, **kwargs):
            request = LLMRequest(messages=[...])
            response = llm_client.complete(request)
            return response.content
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from ai_engine.models.skill import Skill
from ai_engine.types import SkillCategory

if TYPE_CHECKING:
    from ai_engine.events.bus import EventBus
    from ai_engine.services.llm.base import LLMClient

logger = logging.getLogger(__name__)


class BaseSkill(ABC):
    """
    Classe de base abstraite pour tous les Skills concrets.

    Sous-classer cette classe pour créer un skill :
      - Définir les attributs de classe : key, name, description, category
      - Déclarer required_tool_keys (liste de clés tools nécessaires)
      - Implémenter run(**kwargs) — reçoit toujours llm_client via kwarg
      - Optionnellement surcharger arun(**kwargs) pour une version async native

    L'EventBus est optionnel : si fourni (inject_event_bus), des événements
    SkillStarted/Completed/Failed seront automatiquement émis.
    """

    # ── Attributs de classe à redéfinir ──────────────────────────────────────
    key: str = ""
    name: str = ""
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    required_tool_keys: list[str] = []
    is_active: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if ABC not in cls.__bases__ and not cls.key:
            raise TypeError(
                f"Skill class '{cls.__name__}' must define a non-empty 'key' attribute."
            )

    def __init__(self, event_bus: EventBus | None = None) -> None:
        self._event_bus = event_bus

    # ── Interface publique ────────────────────────────────────────────────────

    @abstractmethod
    def run(
        self,
        *,
        llm_client: LLMClient,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Exécute le skill de manière synchrone.

        Args:
            llm_client: Client LLM à utiliser pour le raisonnement
            agent_id: ID de l'agent appelant (pour l'EventBus)
            conversation_id: ID de la conversation (pour l'EventBus)
            **kwargs: Paramètres spécifiques au skill

        Returns:
            Résultat du skill (str, dict, list, etc.)
        """

    async def arun(
        self,
        *,
        llm_client: LLMClient,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Exécute le skill de manière asynchrone.

        Par défaut, délègue à run() dans un thread pool.
        Surcharger pour une implémentation async native.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.run(
                llm_client=llm_client,
                agent_id=agent_id,
                conversation_id=conversation_id,
                **kwargs,
            ),
        )

    def execute(
        self,
        *,
        llm_client: LLMClient,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Point d'entrée principal (sync) avec émission d'événements.

        Appeler cette méthode plutôt que run() pour bénéficier
        des événements EventBus automatiques.
        """
        from ai_engine.events.events import (
            SkillCompletedEvent,
            SkillFailedEvent,
            SkillStartedEvent,
        )

        start = time.monotonic()
        self._emit(
            SkillStartedEvent(
                skill_key=self.key,
                skill_name=self.name,
                agent_id=agent_id,
                conversation_id=conversation_id,
            )
        )

        try:
            result = self.run(
                llm_client=llm_client,
                agent_id=agent_id,
                conversation_id=conversation_id,
                **kwargs,
            )
            duration_ms = (time.monotonic() - start) * 1000
            self._emit(
                SkillCompletedEvent(
                    skill_key=self.key,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    duration_ms=duration_ms,
                )
            )
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            self._emit(
                SkillFailedEvent(
                    skill_key=self.key,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    error=str(exc),
                    duration_ms=duration_ms,
                )
            )
            raise

    async def aexecute(
        self,
        *,
        llm_client: LLMClient,
        agent_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """
        Point d'entrée principal (async) avec émission d'événements.
        """
        from ai_engine.events.events import (
            SkillCompletedEvent,
            SkillFailedEvent,
            SkillStartedEvent,
        )

        start = time.monotonic()
        await self._aemit(
            SkillStartedEvent(
                skill_key=self.key,
                skill_name=self.name,
                agent_id=agent_id,
                conversation_id=conversation_id,
            )
        )

        try:
            result = await self.arun(
                llm_client=llm_client,
                agent_id=agent_id,
                conversation_id=conversation_id,
                **kwargs,
            )
            duration_ms = (time.monotonic() - start) * 1000
            await self._aemit(
                SkillCompletedEvent(
                    skill_key=self.key,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    duration_ms=duration_ms,
                )
            )
            return result
        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            await self._aemit(
                SkillFailedEvent(
                    skill_key=self.key,
                    agent_id=agent_id,
                    conversation_id=conversation_id,
                    error=str(exc),
                    duration_ms=duration_ms,
                )
            )
            raise

    # ── SkillDefinition ───────────────────────────────────────────────────────

    @property
    def definition(self) -> Skill:
        """Retourne le modèle Pydantic Skill associé à ce skill."""
        return Skill(
            key=self.key,
            name=self.name,
            description=self.description,
            category=self.category,
            required_tool_ids=self.required_tool_keys,
            is_active=self.is_active,
        )

    # ── EventBus helpers ──────────────────────────────────────────────────────

    def inject_event_bus(self, bus: EventBus) -> None:
        """Injecte un EventBus pour l'émission d'événements."""
        self._event_bus = bus

    def _emit(self, event: Any) -> None:
        if self._event_bus is not None:
            self._event_bus.emit(event)

    async def _aemit(self, event: Any) -> None:
        if self._event_bus is not None:
            await self._event_bus.aemit(event)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} key={self.key!r}>"
