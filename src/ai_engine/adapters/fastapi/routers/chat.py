"""
AI Engine FastAPI — /chat router.

POST /chat         — envoie un message, retourne la réponse JSON
POST /chat/stream  — envoie un message, retourne la réponse en streaming SSE
"""

from __future__ import annotations

import json
from typing import AsyncGenerator

try:
    from fastapi import APIRouter, HTTPException
    from fastapi.responses import StreamingResponse
except ImportError as e:
    raise ImportError("Install with: pip install ai-engine[fastapi]") from e

from ai_engine.adapters.fastapi.dependencies import AgentServiceDep, StorageDep
from ai_engine.adapters.fastapi.schemas import ChatRequest, ChatResponse

router = APIRouter()


def _resolve_agent(storage: object, agent_id: str) -> object:
    """Résout par ID exact ou slug."""
    s = storage  # type: ignore[assignment]
    agent = s.get_agent(agent_id) or s.get_agent_by_slug(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found.")
    return agent


@router.post("", response_model=ChatResponse, summary="Send a message to an agent")
def chat(body: ChatRequest, svc: AgentServiceDep, storage: StorageDep) -> ChatResponse:
    """
    Envoie un message à un agent et retourne sa réponse.

    - Si `conversation_id` est fourni, le message est ajouté à la conversation existante.
    - Sinon, une nouvelle conversation est créée automatiquement.
    """
    agent = _resolve_agent(storage, body.agent_id)

    try:
        from ai_engine.exceptions import AgentError

        response_msg, conv = svc.chat(
            agent.id,
            body.message,
            conversation_id=body.conversation_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {e}") from e

    return ChatResponse(
        conversation_id=conv.id,
        message_id=response_msg.id,
        content=response_msg.content,
        role=response_msg.role,
        agent_id=agent.id,
    )


@router.post("/stream", summary="Send a message and stream the response (SSE)")
async def chat_stream(
    body: ChatRequest, svc: AgentServiceDep, storage: StorageDep
) -> StreamingResponse:
    """
    Envoie un message à un agent et stream la réponse en Server-Sent Events.

    Format SSE :
        data: {"delta": "...", "done": false}\\n\\n
        data: {"delta": "", "done": true, "conversation_id": "...", "message_id": "..."}\\n\\n
    """
    agent = _resolve_agent(storage, body.agent_id)

    async def _event_generator() -> AsyncGenerator[str, None]:
        try:
            # ai_engine's chat() is synchronous — run in threadpool to avoid
            # blocking the event loop.
            import asyncio

            loop = asyncio.get_event_loop()
            response_msg, conv = await loop.run_in_executor(
                None,
                lambda: svc.chat(
                    agent.id,
                    body.message,
                    conversation_id=body.conversation_id,
                ),
            )

            # Simulate token-by-token streaming by chunking the response.
            # Replace this with a real streaming LLM call when available.
            content = response_msg.content
            chunk_size = 8
            for i in range(0, len(content), chunk_size):
                chunk = content[i : i + chunk_size]
                payload = json.dumps({"delta": chunk, "done": False})
                yield f"data: {payload}\n\n"

            # Final event with metadata
            final = json.dumps(
                {
                    "delta": "",
                    "done": True,
                    "conversation_id": conv.id,
                    "message_id": response_msg.id,
                    "agent_id": agent.id,
                }
            )
            yield f"data: {final}\n\n"

        except Exception as e:
            error_payload = json.dumps({"error": str(e), "done": True})
            yield f"data: {error_payload}\n\n"

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
