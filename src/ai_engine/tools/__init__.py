"""
AI Engine — Tool System.

Système d'exécution de tools pour le function calling :
- BaseTool      : classe de base abstraite pour implémenter des tools
- ToolRegistry  : enregistrement et résolution des fonctions
- ToolExecutor  : exécution sécurisée et boucle tool-calling

Outils intégrés :
- CalculatorTool      : évaluation d'expressions mathématiques
- DuckDuckGoSearchTool: recherche web (sans clé API)
- SerperSearchTool    : recherche Google via Serper
- HttpGetTool         : requêtes HTTP GET
- HttpPostTool        : requêtes HTTP POST

Usage:
    from ai_engine.tools import ToolRegistry, ToolExecutor, CalculatorTool

    registry = ToolRegistry()
    calc = CalculatorTool()
    registry.register_tool(calc.definition, calc.run)

    executor = ToolExecutor(registry)
    result = executor.execute_call(tool_call)
"""

from __future__ import annotations

__all__ = [
    # Core
    "BaseTool",
    "ToolRegistry",
    "ToolExecutor",
    # Built-in tools
    "CalculatorTool",
    "DuckDuckGoSearchTool",
    "SerperSearchTool",
    "HttpGetTool",
    "HttpPostTool",
]

from ai_engine.tools.base import BaseTool
from ai_engine.tools.calculator import CalculatorTool
from ai_engine.tools.executor import ToolExecutor
from ai_engine.tools.http_client import HttpGetTool, HttpPostTool
from ai_engine.tools.registry import ToolRegistry
from ai_engine.tools.web_search import DuckDuckGoSearchTool, SerperSearchTool
