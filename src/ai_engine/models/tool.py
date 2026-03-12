"""
AI Engine Models — Tool (Tool Definition for Function Calling).

Conversion du modèle Django `Tool` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/tool.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ai_engine.types import ToolType


class ToolDefinition(BaseModel):
    """
    Définition d'un outil technique utilisable par un Agent.

    Équivalent standalone du modèle Django `Tool`.
    Un Tool est une opération atomique (API call, DB query, file read, etc.).

    Usage:
        tool = ToolDefinition(
            key="web_search",
            name="Web Search",
            description="Search the web for information",
            tool_type=ToolType.API,
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    key: str = Field(
        ...,
        description="Identifiant unique du tool (ex: web_search, send_email)",
    )
    name: str
    description: str = Field(
        default="",
        description="Description pour le LLM (utilisée dans function calling)",
    )

    # Type
    tool_type: ToolType = ToolType.FUNCTION

    # Schema JSON pour les paramètres (OpenAI function calling format)
    parameters_schema: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON Schema des paramètres (format OpenAI function calling)",
    )

    # Implémentation
    function_path: str = Field(
        default="",
        description="Chemin Python vers la fonction (ex: ai_engine.tools.web_search.execute)",
    )

    # Connector lié (optionnel)
    connector_id: str | None = Field(
        default=None,
        description="ID du Connector lié (si tool_type=connector)",
    )

    # Configuration
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Configuration du tool (headers, auth, etc.)",
    )

    # Sécurité
    requires_approval: bool = Field(
        default=False,
        description="Nécessite une approbation humaine avant exécution",
    )
    is_dangerous: bool = Field(
        default=False,
        description="Opération potentiellement destructrice (DELETE, DROP, etc.)",
    )

    # État
    is_active: bool = True

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get_function_schema(self) -> dict[str, Any]:
        """Retourne le schema au format OpenAI function calling."""
        return {
            "type": "function",
            "function": {
                "name": self.key,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
