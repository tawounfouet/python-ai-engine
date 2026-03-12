"""
AI Engine Models — Message (Conversation Messages).

Conversion du modèle Django `AgentMessage` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/message.py

Le JSONField `metadata` de Django est éclaté en types forts :
  - `tool_calls: list[ToolCall]` — appels de fonction
  - `tool_result: ToolResult | None` — résultat d'un appel de fonction
  - `token_usage: TokenUsage | None` — métriques de tokens
  - `metadata: dict` — métadonnées libres restantes
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import MessageRole


class ToolCall(BaseModel):
    """
    Représentation d'un appel de fonction (function calling).

    Compatible avec le format OpenAI tool_calls.
    """

    id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="ID unique de l'appel de tool (ex: call_abc123)",
    )
    name: str = Field(
        ...,
        description="Nom de la fonction appelée (ex: web_search)",
    )
    arguments: dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments passés à la fonction (parsed JSON)",
    )


class ToolResult(BaseModel):
    """
    Résultat d'un appel de fonction.

    Associé à un ToolCall via `tool_call_id`.
    """

    tool_call_id: str = Field(
        ...,
        description="ID du ToolCall auquel ce résultat répond",
    )
    output: str = Field(
        default="",
        description="Résultat de l'appel (texte sérialisé)",
    )
    is_error: bool = Field(
        default=False,
        description="True si l'appel a échoué",
    )


class TokenUsage(BaseModel):
    """
    Métriques d'utilisation de tokens pour un message ou une exécution.
    """

    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(
        default=0.0,
        ge=0.0,
        description="Coût estimé en USD",
    )

    @classmethod
    def from_total(cls, total: int, cost: float = 0.0) -> TokenUsage:
        """Crée un TokenUsage à partir du total uniquement."""
        return cls(total_tokens=total, estimated_cost_usd=cost)


class Message(BaseModel):
    """
    Message dans une conversation avec un Agent.

    Équivalent standalone du modèle Django `AgentMessage`.

    Le champ `metadata` opaque de Django est éclaté en sous-modèles typés :
      - `tool_calls` pour les appels de fonction
      - `tool_result` pour les résultats de fonction
      - `token_usage` pour les métriques

    Usage:
        # Message utilisateur
        msg = Message(
            conversation_id="conv-uuid",
            role=MessageRole.USER,
            content="What is quantum computing?",
        )

        # Message assistant avec function calling
        msg = Message(
            conversation_id="conv-uuid",
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[
                ToolCall(name="web_search", arguments={"query": "quantum computing"}),
            ],
        )

        # Message tool result
        msg = Message(
            conversation_id="conv-uuid",
            role=MessageRole.TOOL,
            content="Quantum computing uses qubits...",
            tool_result=ToolResult(
                tool_call_id="call-uuid",
                output="Quantum computing uses qubits...",
            ),
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))

    # Conversation (référence par ID — remplace ForeignKey("ai.Execution"))
    conversation_id: str = Field(
        ...,
        description="ID de la Conversation à laquelle appartient ce message",
    )

    # Rôle
    role: MessageRole

    # Contenu
    content: str = Field(
        default="",
        description="Contenu textuel du message",
    )

    # Function calling — éclaté depuis metadata Django
    tool_calls: list[ToolCall] = Field(
        default_factory=list,
        description="Appels de fonction (si role=assistant)",
    )
    tool_result: ToolResult | None = Field(
        default=None,
        description="Résultat d'un appel de fonction (si role=tool)",
    )

    # Token usage — éclaté depuis le champ `tokens` de Django
    token_usage: TokenUsage | None = Field(
        default=None,
        description="Métriques de tokens pour ce message",
    )

    # Metadata libre (tout ce qui ne rentre pas dans les champs typés)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
