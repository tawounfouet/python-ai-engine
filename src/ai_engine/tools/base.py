"""
AI Engine — BaseTool ABC.

Classe de base abstraite pour implémenter des tools concrets.
Chaque tool encapsule sa ToolDefinition et son implémentation `run()`.

Usage:
    class MyTool(BaseTool):
        key = "my_tool"
        name = "My Tool"
        description = "Does something useful"
        parameters_schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }

        def run(self, query: str) -> str:
            return f"Result for: {query}"

    tool = MyTool()
    result = tool("hello")          # sync call
    result = await tool.arun("hi")  # async call
    registry.register_tool(tool.definition, tool.run)
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Any

from ai_engine.models.tool import ToolDefinition
from ai_engine.types import ToolType

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """
    Classe de base abstraite pour tous les tools concrets.

    Sous-classer cette classe pour créer un tool :
      - Définir les attributs de classe : key, name, description, parameters_schema
      - Implémenter la méthode `run(**kwargs)` (sync obligatoire)
      - Optionnellement surcharger `arun(**kwargs)` pour une version async native
    """

    # ── Attributs de classe à redéfinir ──────────────────────────────────────
    key: str = ""
    name: str = ""
    description: str = ""
    tool_type: ToolType = ToolType.FUNCTION
    parameters_schema: dict[str, Any] = {"type": "object", "properties": {}}
    requires_approval: bool = False
    is_dangerous: bool = False
    is_active: bool = True

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Vérification à la définition de la sous-classe (pas sur BaseTool lui-même)
        if ABC not in cls.__bases__ and not cls.key:
            raise TypeError(
                f"Tool class '{cls.__name__}' must define a non-empty 'key' attribute."
            )

    # ── Interface publique ────────────────────────────────────────────────────

    @abstractmethod
    def run(self, **kwargs: Any) -> Any:
        """
        Exécute le tool de manière synchrone.

        Args:
            **kwargs: Paramètres définis dans parameters_schema

        Returns:
            Résultat du tool (str, dict, list, etc.)
        """

    async def arun(self, **kwargs: Any) -> Any:
        """
        Exécute le tool de manière asynchrone.

        Par défaut, délègue à run() dans un thread pool.
        Surcharger pour une implémentation async native.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self.run(**kwargs))

    def __call__(self, **kwargs: Any) -> Any:
        """Permet d'appeler le tool directement : tool(query="hello")."""
        return self.run(**kwargs)

    # ── ToolDefinition ────────────────────────────────────────────────────────

    @property
    def definition(self) -> ToolDefinition:
        """Retourne la ToolDefinition associée à ce tool."""
        return ToolDefinition(
            key=self.key,
            name=self.name,
            description=self.description,
            tool_type=self.tool_type,
            parameters_schema=self.parameters_schema,
            function_path=f"{self.__class__.__module__}.{self.__class__.__name__}",
            requires_approval=self.requires_approval,
            is_dangerous=self.is_dangerous,
            is_active=self.is_active,
        )

    def get_function_schema(self) -> dict[str, Any]:
        """Retourne le schema OpenAI function calling pour ce tool."""
        return self.definition.get_function_schema()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} key={self.key!r}>"
