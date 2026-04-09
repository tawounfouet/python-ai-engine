"""
AI Engine FastAPI — /agents router.

GET    /agents          — liste tous les agents
POST   /agents          — créer un agent
GET    /agents/{id}     — détail d'un agent
PATCH  /agents/{id}     — mise à jour partielle
DELETE /agents/{id}     — suppression
"""

from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException, status
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e

from ai_engine.adapters.fastapi.dependencies import (
    AgentServiceDep,
    PaginationDep,
    StorageDep,
)
from ai_engine.adapters.fastapi.schemas import (
    AgentCreate,
    AgentResponse,
    AgentUpdate,
    PaginatedResponse,
)

router = APIRouter()


def _to_response(agent: object) -> AgentResponse:
    a = agent  # type: ignore[assignment]
    return AgentResponse(
        id=a.id,
        name=a.name,
        slug=a.slug or "",
        description=a.description or "",
        role=a.role,
        provider_id=a.provider_id,
        system_prompt=a.system_prompt or "",
        is_active=a.is_active,
        created_at=a.created_at,
        updated_at=a.updated_at,
    )


@router.get("", response_model=PaginatedResponse, summary="List agents")
def list_agents(
    storage: StorageDep,
    pagination: PaginationDep,
    active_only: bool = False,
) -> PaginatedResponse:
    agents = storage.list_agents(is_active=True if active_only else None)
    total = len(agents)
    page = agents[pagination.offset : pagination.offset + pagination.limit]
    return PaginatedResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=[_to_response(a) for a in page],
    )


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED, summary="Create agent")
def create_agent(body: AgentCreate, svc: AgentServiceDep) -> AgentResponse:
    from ai_engine.exceptions import ProviderNotFoundError
    from ai_engine.types import AgentRole

    valid_roles = [r.value for r in AgentRole]
    if body.role not in valid_roles:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown role '{body.role}'. Valid: {valid_roles}",
        )
    try:
        agent = svc.create_agent(
            name=body.name,
            provider_id=body.provider_id,
            system_prompt=body.system_prompt,
            role=AgentRole(body.role),
            slug=body.slug,
            description=body.description,
            is_active=body.is_active,
        )
    except ProviderNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse, summary="Get agent")
def get_agent(agent_id: str, storage: StorageDep) -> AgentResponse:
    agent = storage.get_agent(agent_id) or storage.get_agent_by_slug(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return _to_response(agent)


@router.patch("/{agent_id}", response_model=AgentResponse, summary="Update agent")
def update_agent(agent_id: str, body: AgentUpdate, storage: StorageDep) -> AgentResponse:
    from datetime import UTC, datetime

    agent = storage.get_agent(agent_id) or storage.get_agent_by_slug(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")

    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.now(UTC)

    storage.save_agent(agent)
    return _to_response(agent)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete agent")
def delete_agent(agent_id: str, storage: StorageDep) -> None:
    agent = storage.get_agent(agent_id) or storage.get_agent_by_slug(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    storage.delete_agent(agent.id)
