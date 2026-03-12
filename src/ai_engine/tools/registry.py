"""
AI Engine — Tool Registry.

Registre central pour associer les clés de tools à leurs fonctions Python.
Supporte les fonctions sync et async, avec résolution par :
  - enregistrement explicite (register)
  - résolution dynamique via function_path (resolve_from_path)

Usage:
    registry = ToolRegistry()

    # Enregistrement explicite
    registry.register("web_search", my_search_function)

    # Ou avec un ToolDefinition
    registry.register_tool(tool_definition, my_search_function)

    # Résolution
    fn = registry.get("web_search")
    result = fn(query="hello")
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any

from ai_engine.exceptions import ToolNotFoundError
from ai_engine.models.tool import ToolDefinition

logger = logging.getLogger(__name__)

# Type générique pour une fonction tool (sync ou async)
ToolFunction = Callable[..., Any]


class ToolRegistry:
    """Registre de fonctions tool pour le function calling."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolFunction] = {}
        self._definitions: dict[str, ToolDefinition] = {}

    def register(
        self,
        key: str,
        func: ToolFunction,
        definition: ToolDefinition | None = None,
    ) -> None:
        """
        Enregistre une fonction tool sous une clé donnée.

        Args:
            key: Clé unique (ex: "web_search")
            func: Fonction Python à appeler
            definition: ToolDefinition associée (optionnel)
        """
        if not callable(func):
            raise TypeError(f"Tool function for '{key}' must be callable, got {type(func)}")
        self._tools[key] = func
        if definition is not None:
            self._definitions[key] = definition
        logger.debug("Registered tool: %s", key)

    def register_tool(self, definition: ToolDefinition, func: ToolFunction) -> None:
        """
        Enregistre un tool depuis sa ToolDefinition.

        Args:
            definition: Définition du tool (contient la clé)
            func: Implémentation Python
        """
        self.register(definition.key, func, definition=definition)

    def get(self, key: str) -> ToolFunction:
        """
        Récupère la fonction associée à une clé.

        Args:
            key: Clé du tool

        Returns:
            La fonction callable

        Raises:
            ToolNotFoundError: Si la clé n'est pas enregistrée
        """
        fn = self._tools.get(key)
        if fn is None:
            raise ToolNotFoundError(key)
        return fn

    def get_definition(self, key: str) -> ToolDefinition | None:
        """Récupère la ToolDefinition enregistrée (ou None)."""
        return self._definitions.get(key)

    def has(self, key: str) -> bool:
        """True si une fonction est enregistrée sous cette clé."""
        return key in self._tools

    def keys(self) -> list[str]:
        """Liste toutes les clés enregistrées."""
        return list(self._tools.keys())

    def resolve_from_path(self, key: str, function_path: str) -> None:
        """
        Résout et enregistre un tool depuis un chemin Python dotted.

        Ex: "myapp.tools.web_search.execute" → importe et enregistre.

        Args:
            key: Clé sous laquelle enregistrer
            function_path: Chemin dotted vers la fonction

        Raises:
            ImportError: Si le module n'existe pas
            AttributeError: Si la fonction n'existe pas dans le module
        """
        if not function_path:
            raise ValueError(f"Empty function_path for tool '{key}'")

        module_path, _, func_name = function_path.rpartition(".")
        if not module_path:
            raise ValueError(
                f"Invalid function_path '{function_path}' for tool '{key}'. "
                f"Expected format: 'module.path.function_name'"
            )

        module = importlib.import_module(module_path)
        func = getattr(module, func_name)

        if not callable(func):
            raise TypeError(
                f"'{function_path}' resolved to {type(func)}, expected a callable"
            )

        self.register(key, func)
        logger.debug("Resolved tool '%s' from path '%s'", key, function_path)

    def clear(self) -> None:
        """Supprime tous les tools enregistrés."""
        self._tools.clear()
        self._definitions.clear()

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, key: str) -> bool:
        return self.has(key)
