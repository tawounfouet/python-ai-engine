"""
AI Engine CLI — Helpers partagés entre les commandes.

Résolution du storage, des agents, des providers,
et gestion centralisée des erreurs CLI.
"""

from __future__ import annotations

import os
import sys
from typing import Any

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "CLI adapter requires 'typer'. Install with: pip install ai-engine[cli]"
    ) from e

from ai_engine.adapters.cli.console import print_error


# ── Constantes & env ──────────────────────────────────────────────────────────

DEFAULT_DB = os.environ.get("AI_ENGINE_DB", "ai_engine.db")


# ── Storage factory ───────────────────────────────────────────────────────────


def get_storage(db: str) -> Any:
    """Retourne un SQLiteStorage sur le fichier db donné."""
    from ai_engine.storage.sqlite import SQLiteStorage

    return SQLiteStorage(db)


def get_agent_service(db: str) -> Any:
    """Retourne un AgentService prêt à l'emploi."""
    from ai_engine.services.agent import AgentService

    return AgentService(get_storage(db))


# ── Résolveurs (id ou slug) ───────────────────────────────────────────────────


def resolve_agent(storage: Any, identifier: str) -> Any:
    """
    Résout un agent depuis son ID (complet ou préfixe) ou son slug.
    Lève typer.Exit(1) si introuvable.
    """
    # Essai par ID exact
    agent = storage.get_agent(identifier)
    if agent:
        return agent

    # Essai par slug
    agent = storage.get_agent_by_slug(identifier)
    if agent:
        return agent

    # Essai par préfixe d'ID (les 8 premiers chars)
    all_agents = storage.list_agents()
    matches = [a for a in all_agents if a.id.startswith(identifier)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print_error(
            f"Ambiguous identifier '{identifier}': matches {len(matches)} agents. "
            "Use a longer ID prefix."
        )
        raise typer.Exit(1)

    print_error(f"Agent '{identifier}' not found (tried ID, slug, and ID prefix).")
    raise typer.Exit(1)


def resolve_provider(storage: Any, identifier: str) -> Any:
    """
    Résout un provider depuis son ID (complet ou préfixe) ou son nom.
    Lève typer.Exit(1) si introuvable.
    """
    provider = storage.get_provider(identifier)
    if provider:
        return provider

    provider = storage.get_provider_by_name(identifier)
    if provider:
        return provider

    all_providers = storage.list_providers()
    matches = [p for p in all_providers if p.id.startswith(identifier)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print_error(
            f"Ambiguous identifier '{identifier}': matches {len(matches)} providers."
        )
        raise typer.Exit(1)

    print_error(f"Provider '{identifier}' not found (tried ID, name, and ID prefix).")
    raise typer.Exit(1)


def resolve_conversation(storage: Any, identifier: str) -> Any:
    """Résout une conversation par ID exact ou préfixe."""
    conv = storage.get_conversation(identifier)
    if conv:
        return conv

    all_convs = storage.list_conversations()
    matches = [c for c in all_convs if c.id.startswith(identifier)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print_error(f"Ambiguous identifier '{identifier}'.")
        raise typer.Exit(1)

    print_error(f"Conversation '{identifier}' not found.")
    raise typer.Exit(1)


# ── Gestion d'erreurs ─────────────────────────────────────────────────────────


def abort(msg: str, code: int = 1) -> None:
    """Affiche une erreur et quitte proprement."""
    print_error(msg)
    raise typer.Exit(code)
