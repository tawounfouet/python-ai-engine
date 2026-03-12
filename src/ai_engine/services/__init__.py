"""
AI Engine Services Layer.

La couche services fournit l'interface métier de haut niveau pour interagir
avec le système. Elle orchestre les différents composants (storage, LLM providers,
agents, etc.) et expose une API simple pour les applications clientes.

Architecture:
- `llm/` : Clients LLM abstraits et implémentations par provider
- `agent.py` : Service de gestion des agents
- `conversation.py` : Service de gestion des conversations
- `execution.py` : Service d'exécution de tâches
- `memory.py` : Service de gestion de la mémoire des agents
"""

from __future__ import annotations

__all__ = [
    # Core services
    "AgentService",
    # LLM services
    "LLMClient",
    "LLMRequest",
    "LLMResponse",
    "get_llm_client",
    "list_available_providers",
]

from ai_engine.services.agent import AgentService
from ai_engine.services.llm import (
    LLMClient,
    LLMRequest,
    LLMResponse,
    get_llm_client,
    list_available_providers,
)
