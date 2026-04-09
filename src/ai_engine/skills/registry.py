"""
AI Engine — SkillRegistry.

Registre central pour enregistrer, résoudre et exécuter des Skills.

Usage:
    registry = SkillRegistry()
    registry.register(SummarizeSkill())
    registry.register(ResearchSkill())

    skill = registry.get("summarize")
    result = skill.execute(llm_client=client, text="Long article...")

    # Vérifier les tools requis
    missing = registry.get_missing_tools("research", available_tool_keys={"web_search"})
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from ai_engine.exceptions import SkillNotFoundError
from ai_engine.models.skill import Skill
from ai_engine.types import SkillCategory

if TYPE_CHECKING:
    from ai_engine.events.bus import EventBus
    from ai_engine.skills.base import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    """
    Registre de Skills pour ai_engine.

    Centralise l'enregistrement et la résolution des skills disponibles.
    Injecte optionnellement un EventBus dans chaque skill enregistré.
    """

    def __init__(self, event_bus: EventBus | None = None) -> None:
        """
        Args:
            event_bus: EventBus optionnel injecté dans tous les skills enregistrés
        """
        self._skills: dict[str, BaseSkill] = {}
        self._event_bus = event_bus

    # ── Enregistrement ────────────────────────────────────────────────────────

    def register(self, skill: BaseSkill) -> None:
        """
        Enregistre un skill dans le registre.

        Si un EventBus est configuré, il est injecté dans le skill.

        Args:
            skill: Instance de BaseSkill à enregistrer

        Raises:
            ValueError: Si la clé est vide
        """
        if not skill.key:
            raise ValueError(f"Skill '{skill.__class__.__name__}' has an empty key.")

        if self._event_bus is not None:
            skill.inject_event_bus(self._event_bus)

        self._skills[skill.key] = skill
        logger.debug("Registered skill: '%s' (%s)", skill.key, skill.__class__.__name__)

    def register_many(self, skills: list[BaseSkill]) -> None:
        """Enregistre plusieurs skills à la fois."""
        for skill in skills:
            self.register(skill)

    def unregister(self, key: str) -> bool:
        """
        Retire un skill du registre.

        Args:
            key: Clé du skill à retirer

        Returns:
            True si retiré, False si non trouvé
        """
        if key in self._skills:
            del self._skills[key]
            return True
        return False

    # ── Résolution ────────────────────────────────────────────────────────────

    def get(self, key: str) -> BaseSkill:
        """
        Récupère un skill par clé.

        Args:
            key: Clé du skill

        Returns:
            L'instance BaseSkill

        Raises:
            SkillNotFoundError: Si le skill n'est pas enregistré
        """
        skill = self._skills.get(key)
        if skill is None:
            raise SkillNotFoundError(key)
        return skill

    def get_or_none(self, key: str) -> BaseSkill | None:
        """Retourne le skill ou None s'il n'est pas trouvé."""
        return self._skills.get(key)

    def has(self, key: str) -> bool:
        """True si un skill est enregistré sous cette clé."""
        return key in self._skills

    def keys(self) -> list[str]:
        """Liste toutes les clés de skills enregistrés."""
        return list(self._skills.keys())

    def list_all(self) -> list[BaseSkill]:
        """Retourne tous les skills enregistrés."""
        return list(self._skills.values())

    def list_active(self) -> list[BaseSkill]:
        """Retourne uniquement les skills actifs."""
        return [s for s in self._skills.values() if s.is_active]

    def list_by_category(self, category: SkillCategory) -> list[BaseSkill]:
        """
        Retourne les skills d'une catégorie donnée.

        Args:
            category: La catégorie de skill à filtrer
        """
        return [s for s in self._skills.values() if s.category == category]

    def get_definitions(self) -> list[Skill]:
        """Retourne les modèles Pydantic Skill de tous les skills enregistrés."""
        return [s.definition for s in self._skills.values()]

    # ── Validation ────────────────────────────────────────────────────────────

    def get_missing_tools(
        self,
        skill_key: str,
        available_tool_keys: set[str],
    ) -> list[str]:
        """
        Retourne les tools requis par un skill qui ne sont pas disponibles.

        Args:
            skill_key: Clé du skill à vérifier
            available_tool_keys: Ensemble des clés tools disponibles

        Returns:
            Liste des clés tools manquantes (vide si tout est OK)

        Raises:
            SkillNotFoundError: Si le skill n'existe pas
        """
        skill = self.get(skill_key)
        return [t for t in skill.required_tool_keys if t not in available_tool_keys]

    def can_execute(
        self,
        skill_key: str,
        available_tool_keys: set[str],
    ) -> bool:
        """
        Vérifie si un skill peut s'exécuter avec les tools disponibles.

        Args:
            skill_key: Clé du skill
            available_tool_keys: Ensemble des clés tools disponibles

        Returns:
            True si tous les tools requis sont disponibles
        """
        return len(self.get_missing_tools(skill_key, available_tool_keys)) == 0

    # ── EventBus ──────────────────────────────────────────────────────────────

    def set_event_bus(self, bus: EventBus) -> None:
        """
        Configure un EventBus et l'injecte dans tous les skills déjà enregistrés.

        Args:
            bus: EventBus à utiliser
        """
        self._event_bus = bus
        for skill in self._skills.values():
            skill.inject_event_bus(bus)

    # ── Utilitaires ───────────────────────────────────────────────────────────

    def clear(self) -> None:
        """Supprime tous les skills enregistrés."""
        self._skills.clear()

    def __len__(self) -> int:
        return len(self._skills)

    def __contains__(self, key: str) -> bool:
        return self.has(key)

    def __repr__(self) -> str:
        keys = ", ".join(self._skills.keys())
        return f"<SkillRegistry skills=[{keys}]>"
