"""
AI Engine FastAPI Adapter — Pydantic schemas.

Séparés des domain models pour :
- Contrôler exactement ce qu'on expose à l'API (pas de fuite d'api_key, etc.)
- Versionner l'API indépendamment des models internes
- Supporter les champs de création (sans id/timestamps) et les réponses (avec)

Convention:
  <Entity>Create   — body d'une requête POST
  <Entity>Update   — body d'une requête PATCH (tous champs optionnels)
  <Entity>Response — corps d'une réponse (lecture seule)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ── Pagination ────────────────────────────────────────────────────────────────


class PaginatedResponse(BaseModel):
    """Enveloppe générique pour les listes paginées."""

    total: int
    limit: int
    offset: int
    items: list[Any]


# ── Provider schemas ──────────────────────────────────────────────────────────


class ProviderCreate(BaseModel):
    name: str = Field(..., description="Nom d'affichage du provider")
    provider_type: str = Field(..., description="Type (openai, anthropic, ollama, …)")
    default_model: str = Field(..., description="Modèle par défaut (ex: gpt-4o)")
    api_key: Optional[str] = Field(
        None, description="Clé API (non retournée dans les réponses)"
    )
    api_base_url: Optional[str] = Field(None, description="URL de base personnalisée")
    is_default: bool = False
    is_active: bool = True


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    default_model: Optional[str] = None
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


class ProviderResponse(BaseModel):
    id: str
    name: str
    provider_type: str
    default_model: str
    api_base_url: Optional[str]
    is_active: bool
    is_default: bool
    has_api_key: bool = Field(..., description="True si une clé API est configurée")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Agent schemas ─────────────────────────────────────────────────────────────


class AgentCreate(BaseModel):
    name: str
    provider_id: str = Field(..., description="ID du provider LLM")
    system_prompt: str = ""
    role: str = "assistant"
    slug: Optional[str] = None
    description: str = ""
    is_active: bool = True


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    system_prompt: Optional[str] = None
    role: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    provider_id: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    role: str
    provider_id: str
    system_prompt: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Conversation schemas ──────────────────────────────────────────────────────


class ConversationCreate(BaseModel):
    agent_id: str
    title: str = ""
    owner_id: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationResponse(BaseModel):
    id: str
    title: str
    agent_id: str
    owner_id: Optional[str]
    status: str
    message_count: int
    total_tokens: int
    last_message_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Message schemas ───────────────────────────────────────────────────────────


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Chat schemas ──────────────────────────────────────────────────────────────


class ChatRequest(BaseModel):
    agent_id: str = Field(..., description="ID (ou slug) de l'agent à interroger")
    message: str = Field(..., min_length=1, description="Message de l'utilisateur")
    conversation_id: Optional[str] = Field(
        None,
        description="Reprendre une conversation existante (créée automatiquement si absent)",
    )
    stream: bool = Field(
        False,
        description="Activer le streaming SSE (Server-Sent Events)",
    )


class ChatResponse(BaseModel):
    conversation_id: str
    message_id: str
    content: str
    role: str = "assistant"
    agent_id: str
