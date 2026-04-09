"""
AI Engine — FastAPI Adapter (Phase 5.2).

Expose ai_engine comme un ensemble de routers FastAPI montables
dans n'importe quelle application existante.

Usage minimal:
    from fastapi import FastAPI
    from ai_engine.adapters.fastapi import create_router

    app = FastAPI()
    app.include_router(create_router("ai_engine.db"), prefix="/ai")

Usage avancé (storage custom):
    from ai_engine.storage.sqlite import SQLiteStorage
    from ai_engine.adapters.fastapi import create_router

    storage = SQLiteStorage("my_app.db")
    router = create_router(storage=storage)
    app.include_router(router, prefix="/api/v1/ai")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


def create_router(
    db: str = "ai_engine.db",
    storage: Any = None,
    prefix: str = "",
    tags_prefix: str = "",
) -> Any:
    """
    Crée et retourne un APIRouter FastAPI avec toutes les routes ai_engine.

    Args:
        db:          Chemin vers le fichier SQLite (ignoré si storage est fourni).
        storage:     Instance StorageBackend custom (prioritaire sur db).
        prefix:      Préfixe URL commun à toutes les routes du router.
        tags_prefix: Préfixe ajouté aux tags OpenAPI (ex: "AI" → "AI Providers").

    Returns:
        APIRouter FastAPI prêt à être monté.
    """
    try:
        from fastapi import APIRouter
    except ImportError as e:
        raise ImportError(
            "FastAPI adapter requires 'fastapi'. "
            "Install with: pip install ai-engine[fastapi]"
        ) from e

    from ai_engine.adapters.fastapi.routers import (
        agents,
        chat,
        conversations,
        providers,
    )

    router = APIRouter(prefix=prefix)

    def _tag(name: str) -> str:
        return f"{tags_prefix} {name}".strip() if tags_prefix else name

    # Inject storage config into sub-routers via app state workaround:
    # each sub-router reads from the dependency injector.
    router.include_router(
        providers.router, prefix="/providers", tags=[_tag("Providers")]
    )
    router.include_router(agents.router, prefix="/agents", tags=[_tag("Agents")])
    router.include_router(
        conversations.router, prefix="/conversations", tags=[_tag("Conversations")]
    )
    router.include_router(chat.router, prefix="/chat", tags=[_tag("Chat")])

    # Attach db/storage config as router state so dependencies can read it
    router.state = type("RouterState", (), {"db": db, "storage": storage})()  # type: ignore[attr-defined]

    return router


__all__ = ["create_router"]
