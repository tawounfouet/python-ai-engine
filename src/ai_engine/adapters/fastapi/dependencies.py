"""
AI Engine FastAPI Adapter — Dependency injection.

Toutes les dépendances FastAPI (Depends) utilisées par les routers.

Usage dans un router:
    from ai_engine.adapters.fastapi.dependencies import StorageDep, AgentServiceDep

    @router.get("/agents")
    def list_agents(storage: StorageDep) -> list[AgentResponse]:
        ...
"""

from __future__ import annotations

import os
from typing import Annotated, Any, Generator

try:
    from fastapi import Depends, Query
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e


# ── Storage dependency ────────────────────────────────────────────────────────


def get_storage(
    db: str = os.environ.get("AI_ENGINE_DB", "ai_engine.db"),
) -> Generator[Any, None, None]:
    """
    FastAPI dependency — retourne un StorageBackend.

    Le chemin DB est lu depuis la query-string ?db=… (override),
    ou depuis la variable d'environnement AI_ENGINE_DB,
    ou depuis la valeur par défaut "ai_engine.db".
    """
    from ai_engine.storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(db)
    try:
        yield storage
    finally:
        pass  # SQLiteStorage is synchronous; no async cleanup needed


StorageDep = Annotated[Any, Depends(get_storage)]


# ── AgentService dependency ───────────────────────────────────────────────────


def get_agent_service(storage: StorageDep) -> Any:
    """FastAPI dependency — retourne un AgentService prêt à l'emploi."""
    from ai_engine.services.agent import AgentService

    return AgentService(storage)


AgentServiceDep = Annotated[Any, Depends(get_agent_service)]


# ── Pagination dependency ─────────────────────────────────────────────────────


class Pagination:
    def __init__(
        self,
        limit: int = Query(
            default=50, ge=1, le=500, description="Nombre max de résultats"
        ),
        offset: int = Query(default=0, ge=0, description="Décalage pour la pagination"),
    ) -> None:
        self.limit = limit
        self.offset = offset


PaginationDep = Annotated[Pagination, Depends(Pagination)]
