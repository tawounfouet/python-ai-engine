"""
AI Engine — Tool System.

Système d'exécution de tools pour le function calling :
- ToolRegistry  : enregistrement et résolution des fonctions
- ToolExecutor  : exécution sécurisée et boucle tool-calling

Usage:
    from ai_engine.tools import ToolRegistry, ToolExecutor

    registry = ToolRegistry()
    registry.register("web_search", my_search_fn)

    executor = ToolExecutor(registry)
    result = executor.execute_call(tool_call)
"""

from __future__ import annotations

__all__ = [
    "ToolRegistry",
    "ToolExecutor",
]

from ai_engine.tools.executor import ToolExecutor
from ai_engine.tools.registry import ToolRegistry
