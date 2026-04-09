"""
AI Engine FastAPI Adapter — Exception handlers.

Convertit les exceptions domain (AgentNotFoundError, etc.)
en réponses HTTP appropriées.

Usage:
    from ai_engine.adapters.fastapi.exception_handlers import register_handlers
    register_handlers(app)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e

from ai_engine.exceptions import (
    AgentError,
    AgentNotFoundError,
    ProviderNotFoundError,
)


async def _agent_not_found_handler(
    request: Request, exc: AgentNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"detail": str(exc), "type": "agent_not_found"}
    )


async def _provider_not_found_handler(
    request: Request, exc: ProviderNotFoundError
) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"detail": str(exc), "type": "provider_not_found"}
    )


async def _agent_error_handler(request: Request, exc: AgentError) -> JSONResponse:
    return JSONResponse(
        status_code=500, content={"detail": str(exc), "type": "agent_error"}
    )


def register_handlers(app: FastAPI) -> None:
    """Enregistre tous les exception handlers ai_engine sur l'app FastAPI."""
    app.add_exception_handler(AgentNotFoundError, _agent_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(ProviderNotFoundError, _provider_not_found_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AgentError, _agent_error_handler)  # type: ignore[arg-type]
