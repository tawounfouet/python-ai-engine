"""
AI Engine — CLI Adapter (Typer + Rich).

Expose ai_engine comme une application en ligne de commande complète.

Usage:
    # Après installation avec pip install ai-engine[cli]
    ai-engine --help
    ai-engine agent list
    ai-engine provider add --name "OpenAI" --type openai --model gpt-4o --key sk-...
    ai-engine chat --agent my-agent "Bonjour !"

Ou via uv run :
    uv run ai-engine agent list
"""

from __future__ import annotations

from ai_engine.adapters.cli.app import app

__all__ = ["app"]
