"""
AI Engine FastAPI — /providers router.

GET    /providers          — liste tous les providers
POST   /providers          — créer un provider
GET    /providers/{id}     — détail d'un provider
PATCH  /providers/{id}     — mise à jour partielle
DELETE /providers/{id}     — suppression
"""

from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException, status
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e

from ai_engine.adapters.fastapi.dependencies import PaginationDep, StorageDep
from ai_engine.adapters.fastapi.schemas import (
    PaginatedResponse,
    ProviderCreate,
    ProviderResponse,
    ProviderUpdate,
)

router = APIRouter()


def _to_response(provider: object) -> ProviderResponse:
    """Convertit un LLMProviderConfig en ProviderResponse (sans api_key)."""
    p = provider  # type: ignore[assignment]
    return ProviderResponse(
        id=p.id,
        name=p.name,
        provider_type=p.provider_type,
        default_model=p.default_model,
        api_base_url=p.api_base_url,
        is_active=p.is_active,
        is_default=p.is_default,
        has_api_key=p.api_key is not None,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


@router.get("", response_model=PaginatedResponse, summary="List providers")
def list_providers(
    storage: StorageDep,
    pagination: PaginationDep,
    active_only: bool = False,
) -> PaginatedResponse:
    providers = storage.list_providers(is_active=True if active_only else None)
    total = len(providers)
    page = providers[pagination.offset : pagination.offset + pagination.limit]
    return PaginatedResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=[_to_response(p) for p in page],
    )


@router.post(
    "",
    response_model=ProviderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create provider",
)
def create_provider(body: ProviderCreate, storage: StorageDep) -> ProviderResponse:
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.types import ProviderType
    from pydantic import SecretStr

    valid_types = [t.value for t in ProviderType]
    if body.provider_type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown provider_type '{body.provider_type}'. Valid: {valid_types}",
        )

    provider = LLMProviderConfig(
        name=body.name,
        provider_type=ProviderType(body.provider_type),
        default_model=body.default_model,
        api_key=SecretStr(body.api_key) if body.api_key else None,
        api_base_url=body.api_base_url,
        is_default=body.is_default,
        is_active=body.is_active,
    )
    storage.save_provider(provider)
    return _to_response(provider)


@router.get("/{provider_id}", response_model=ProviderResponse, summary="Get provider")
def get_provider(provider_id: str, storage: StorageDep) -> ProviderResponse:
    provider = storage.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found."
        )
    return _to_response(provider)


@router.patch(
    "/{provider_id}", response_model=ProviderResponse, summary="Update provider"
)
def update_provider(
    provider_id: str, body: ProviderUpdate, storage: StorageDep
) -> ProviderResponse:
    from datetime import UTC, datetime
    from pydantic import SecretStr

    provider = storage.get_provider(provider_id)
    if not provider:
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found."
        )

    update_data = body.model_dump(exclude_none=True)
    if "api_key" in update_data:
        update_data["api_key"] = SecretStr(update_data["api_key"])
    for field, value in update_data.items():
        setattr(provider, field, value)
    provider.updated_at = datetime.now(UTC)

    storage.save_provider(provider)
    return _to_response(provider)


@router.delete(
    "/{provider_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete provider"
)
def delete_provider(provider_id: str, storage: StorageDep) -> None:
    if not storage.get_provider(provider_id):
        raise HTTPException(
            status_code=404, detail=f"Provider '{provider_id}' not found."
        )
    storage.delete_provider(provider_id)
