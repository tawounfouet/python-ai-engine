"""
AI Engine — Skills System.

Capacités de haut niveau pour les agents, combinant outils + LLM.

Composants :
  - BaseSkill     : classe de base abstraite pour implémenter des skills
  - SkillRegistry : registre central pour enregistrer et résoudre des skills

Usage:
    from ai_engine.skills import BaseSkill, SkillRegistry

    class SummarizeSkill(BaseSkill):
        key = "summarize"
        name = "Summarize"
        description = "Summarizes a given text."
        category = SkillCategory.CUSTOM

        def run(self, *, llm_client, text: str, **kwargs) -> str:
            from ai_engine.services.llm.base import LLMRequest
            from ai_engine.models.message import Message
            from ai_engine.types import MessageRole
            request = LLMRequest(messages=[
                Message(role=MessageRole.USER, content=f"Summarize: {text}")
            ])
            return llm_client.complete(request).content

    registry = SkillRegistry()
    registry.register(SummarizeSkill())

    skill = registry.get("summarize")
    result = skill.execute(llm_client=my_client, text="Long article...")
"""

from __future__ import annotations

__all__ = [
    "BaseSkill",
    "SkillRegistry",
]

from ai_engine.skills.base import BaseSkill
from ai_engine.skills.registry import SkillRegistry
