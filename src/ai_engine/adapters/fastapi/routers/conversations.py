"""
AI Engine FastAPI — /conversations router.

GET    /conversations                    — liste toutes les conversations
POST   /conversations                    — créer une conversation
GET    /conversations/{id}               — détail d'une conversation
DELETE /conversations/{id}               — suppression
GET    /conversations/{id}/messages      — historique des messages
"""

from __future__ import annotations

from typing import Optional

try:
    from fastapi import APIRouter, HTTPException, Query, status
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e

from ai_engine.adapters.fastapi.dependencies import PaginationDep, StorageDep
from ai_engine.adapters.fastapi.schemas import (
    ConversationCreate,
    ConversationResponse,
    MessageResponse,
    PaginatedResponse,
)

router = APIRouter()


def _conv_to_response(conv: object) -> ConversationResponse:
    c = conv  # type: ignore[assignment]
    return ConversationResponse(
        id=c.id,
        title=c.title or "",
        agent_id=c.agent_id,
        owner_id=c.owner_id,
        status=c.status,
        message_count=c.message_count,
        total_tokens=c.total_tokens,
        last_message_at=c.last_message_at,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _msg_to_response(msg: object) -> MessageResponse:
    m = msg  # type: ignore[assignment]
    return MessageResponse(
        id=m.id,
        conversation_id=m.conversation_id,
        role=m.role,
        content=m.content,
        created_at=m.created_at,
    )


@router.get("", response_model=PaginatedResponse, summary="List conversations")
def list_conversations(
    storage: StorageDep,
    pagination: PaginationDep,
    agent_id: Optional[str] = Query(None, description="Filtrer par agent"),
) -> PaginatedResponse:
    conversations = storage.list_conversations(agent_id=agent_id)
    total = len(conversations)
    page = conversations[pagination.offset : pagination.offset + pagination.limit]
    return PaginatedResponse(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset,
        items=[_conv_to_response(c) for c in page],
    )


@router.post(
    "",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create conversation",
)
def create_conversation(
    body: ConversationCreate, storage: StorageDep
) -> ConversationResponse:
    if not storage.get_agent(body.agent_id):
        raise HTTPException(
            status_code=404, detail=f"Agent '{body.agent_id}' not found."
        )

    from ai_engine.models.conversation import Conversation

    conv = Conversation(
        agent_id=body.agent_id,
        title=body.title,
        owner_id=body.owner_id,
        metadata=body.metadata,
    )
    storage.save_conversation(conv)
    return _conv_to_response(conv)


@router.get(
    "/{conversation_id}",
    response_model=ConversationResponse,
    summary="Get conversation",
)
def get_conversation(conversation_id: str, storage: StorageDep) -> ConversationResponse:
    conv = storage.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=404, detail=f"Conversation '{conversation_id}' not found."
        )
    return _conv_to_response(conv)


@router.delete(
    "/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete conversation",
)
def delete_conversation(conversation_id: str, storage: StorageDep) -> None:
    if not storage.get_conversation(conversation_id):
        raise HTTPException(
            status_code=404, detail=f"Conversation '{conversation_id}' not found."
        )
    storage.delete_conversation(conversation_id)


@router.get(
    "/{conversation_id}/messages",
    response_model=PaginatedResponse,
    summary="List messages",
)
def list_messages(
    conversation_id: str,
    storage: StorageDep,
    pagination: PaginationDep,
) -> PaginatedResponse:
    if not storage.get_conversation(conversation_id):
        raise HTTPException(
            status_code=404, detail=f"Conversation '{conversation_id}' not found."
        )
    messages = storage.get_messages(
        conversation_id, limit=pagination.limit, offset=pagination.offset
    )
    # get_messages already paginates; for total we fetch count separately
    all_messages = storage.get_messages(conversation_id)
    return PaginatedResponse(
        total=len(all_messages),
        limit=pagination.limit,
        offset=pagination.offset,
        items=[_msg_to_response(m) for m in messages],
    )
