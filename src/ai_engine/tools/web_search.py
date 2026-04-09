"""
AI Engine — Web Search Tool.

Tool de recherche web avec deux backends :
  - DuckDuckGoSearchTool  : utilise l'API DuckDuckGo (sans clé API)
  - SerperSearchTool      : utilise l'API Serper (Google Search, nécessite SERPER_API_KEY)

Usage:
    from ai_engine.tools.web_search import DuckDuckGoSearchTool

    tool = DuckDuckGoSearchTool(max_results=5)
    results = tool(query="Python asyncio tutorial")
    # → "1. Title — snippet (url)\n2. ..."
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from ai_engine.tools.base import BaseTool
from ai_engine.types import ToolType

logger = logging.getLogger(__name__)

_WEB_SEARCH_SCHEMA = {
    "type": "object",
    "properties": {
        "query": {
            "type": "string",
            "description": "The search query to look up on the web.",
        },
        "max_results": {
            "type": "integer",
            "description": "Maximum number of results to return (default: 5).",
            "default": 5,
        },
    },
    "required": ["query"],
}


class DuckDuckGoSearchTool(BaseTool):
    """
    Recherche web via l'API DuckDuckGo Instant Answer (sans clé API).

    Limitations:
      - Résultats limités aux « Instant Answers » (topics, relateds).
      - Pour des résultats web complets, utiliser SerperSearchTool.
    """

    key = "web_search"
    name = "Web Search (DuckDuckGo)"
    description = (
        "Search the web using DuckDuckGo. Returns a list of results with titles, "
        "snippets, and URLs. Use this tool to find current information, facts, "
        "documentation, or any topic available online."
    )
    tool_type = ToolType.API
    parameters_schema = _WEB_SEARCH_SCHEMA

    def __init__(self, max_results: int = 5, timeout: int = 10) -> None:
        self.max_results = max_results
        self.timeout = timeout

    def run(self, query: str, max_results: int | None = None, **_: Any) -> str:
        """
        Effectue une recherche DuckDuckGo.

        Args:
            query: La requête de recherche
            max_results: Nombre max de résultats (override du défaut de l'instance)

        Returns:
            Résultats formatés en texte
        """
        n = max_results or self.max_results
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json&no_html=1&skip_disambig=1"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ai-engine/1.0"})
            with urllib.request.urlopen(
                req, timeout=self.timeout
            ) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
            return f"Error: web search failed — {exc}"

        results: list[str] = []

        # AbstractText (résumé direct)
        if data.get("AbstractText"):
            source = data.get("AbstractURL", "")
            results.append(f"Summary: {data['AbstractText']}\nSource: {source}")

        # RelatedTopics
        for topic in data.get("RelatedTopics", []):
            if len(results) >= n:
                break
            if isinstance(topic, dict) and "Text" in topic:
                text = topic["Text"]
                link = topic.get("FirstURL", "")
                results.append(f"- {text}\n  {link}")
            elif isinstance(topic, dict) and "Topics" in topic:
                # Sous-groupes
                for sub in topic.get("Topics", []):
                    if len(results) >= n:
                        break
                    text = sub.get("Text", "")
                    link = sub.get("FirstURL", "")
                    if text:
                        results.append(f"- {text}\n  {link}")

        if not results:
            return f"No results found for: '{query}'"

        header = f"Search results for '{query}':\n\n"
        return header + "\n".join(results[:n])


class SerperSearchTool(BaseTool):
    """
    Recherche web via l'API Serper (Google Search).

    Nécessite une clé API : https://serper.dev
    Peut être fournie via `api_key` ou la variable d'environnement SERPER_API_KEY.
    """

    key = "web_search"
    name = "Web Search (Serper/Google)"
    description = (
        "Search the web using Google (via Serper API). Returns organic results "
        "with titles, snippets, and URLs. Use for current events, documentation, "
        "facts, or any information available online."
    )
    tool_type = ToolType.API
    parameters_schema = _WEB_SEARCH_SCHEMA

    _SERPER_URL = "https://google.serper.dev/search"

    def __init__(
        self,
        api_key: str = "",
        max_results: int = 5,
        timeout: int = 10,
    ) -> None:
        import os

        self.api_key = api_key or os.environ.get("SERPER_API_KEY", "")
        self.max_results = max_results
        self.timeout = timeout

    def run(self, query: str, max_results: int | None = None, **_: Any) -> str:
        """
        Effectue une recherche Google via Serper.

        Args:
            query: La requête de recherche
            max_results: Nombre max de résultats

        Returns:
            Résultats formatés en texte
        """
        if not self.api_key:
            return (
                "Error: Serper API key not configured. "
                "Set SERPER_API_KEY env var or pass api_key to SerperSearchTool()."
            )

        n = max_results or self.max_results
        payload = json.dumps({"q": query, "num": n}).encode("utf-8")
        headers = {
            "X-API-KEY": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            req = urllib.request.Request(
                self._SERPER_URL, data=payload, headers=headers
            )
            with urllib.request.urlopen(
                req, timeout=self.timeout
            ) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.warning("Serper search failed for '%s': %s", query, exc)
            return f"Error: Serper search failed — {exc}"

        organic = data.get("organic", [])
        if not organic:
            return f"No results found for: '{query}'"

        lines = [f"Search results for '{query}':\n"]
        for i, item in enumerate(organic[:n], start=1):
            title = item.get("title", "")
            snippet = item.get("snippet", "")
            link = item.get("link", "")
            lines.append(f"{i}. {title}\n   {snippet}\n   {link}")

        return "\n".join(lines)
