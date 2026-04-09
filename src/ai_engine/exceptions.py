"""
AI Engine — Exceptions métier typées.

Toutes les exceptions du package sont définies ici.
Jamais de `raise Exception(...)` nu dans le code.
"""

from __future__ import annotations


class AIEngineError(Exception):
    """Exception de base pour tout le package ai_engine."""


# ──────────────────────────────────────────────
# Provider Errors
# ──────────────────────────────────────────────


class ProviderError(AIEngineError):
    """Erreur liée à un provider LLM."""


class LLMError(ProviderError):
    """Erreur lors de l'appel à un LLM."""


class ProviderNotFoundError(ProviderError):
    """Provider introuvable."""

    def __init__(self, provider_id: str) -> None:
        self.provider_id = provider_id
        super().__init__(f"Provider '{provider_id}' not found.")


class UnsupportedProviderError(ProviderError):
    """Type de provider non supporté."""

    def __init__(self, provider_type: str, available: list[str] | None = None) -> None:
        self.provider_type = provider_type
        self.available = available or []
        msg = f"Provider type '{provider_type}' is not supported."
        if self.available:
            msg += f" Available types: {', '.join(self.available)}"
        super().__init__(msg)


class APIKeyMissingError(ProviderError):
    """Clé API manquante pour un provider."""

    def __init__(self, provider_name: str, env_var: str | None = None) -> None:
        self.provider_name = provider_name
        self.env_var = env_var
        msg = f"API key missing for provider '{provider_name}'."
        if env_var:
            msg += f" Set it via provider config or environment variable '{env_var}'."
        super().__init__(msg)


# ──────────────────────────────────────────────
# Agent Errors
# ──────────────────────────────────────────────


class AgentError(AIEngineError):
    """Erreur liée aux agents."""


class AgentNotFoundError(AgentError):
    """Agent introuvable."""

    def __init__(self, agent_id: str) -> None:
        self.agent_id = agent_id
        super().__init__(f"Agent '{agent_id}' not found.")


class AgentDisabledError(AgentError):
    """Agent désactivé."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Agent '{identifier}' is disabled.")


# ──────────────────────────────────────────────
# Conversation Errors
# ──────────────────────────────────────────────


class ConversationError(AIEngineError):
    """Erreur liée à une conversation."""


class ConversationNotFoundError(ConversationError):
    """Conversation introuvable."""

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        super().__init__(f"Conversation '{conversation_id}' not found.")


# ──────────────────────────────────────────────
# Graph Errors
# ──────────────────────────────────────────────


class GraphError(AIEngineError):
    """Erreur liée à un graph."""


class GraphNotFoundError(GraphError):
    """Graph introuvable."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Graph '{identifier}' not found.")


# ──────────────────────────────────────────────
# Execution Errors
# ──────────────────────────────────────────────


class ExecutionError(AIEngineError):
    """Erreur liée à une exécution."""


class ExecutionNotFoundError(ExecutionError):
    """Exécution introuvable."""

    def __init__(self, execution_id: str) -> None:
        self.execution_id = execution_id
        super().__init__(f"Execution '{execution_id}' not found.")


# ──────────────────────────────────────────────
# Tool Errors
# ──────────────────────────────────────────────


class ToolError(AIEngineError):
    """Erreur liée à un tool."""


class ToolNotFoundError(ToolError):
    """Tool introuvable."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Tool '{identifier}' not found.")


class ToolExecutionError(ToolError):
    """Erreur lors de l'exécution d'un tool."""

    def __init__(self, tool_name: str, detail: str) -> None:
        self.tool_name = tool_name
        self.detail = detail
        super().__init__(f"Error executing tool '{tool_name}': {detail}")


# ──────────────────────────────────────────────
# Storage Errors
# ──────────────────────────────────────────────


class StorageError(AIEngineError):
    """Erreur liée au storage."""


class StorageConnectionError(StorageError):
    """Erreur de connexion au storage."""


# ──────────────────────────────────────────────
# Skill Errors
# ──────────────────────────────────────────────


class SkillError(AIEngineError):
    """Erreur liée à un skill."""


class SkillNotFoundError(SkillError):
    """Skill introuvable dans le registre."""

    def __init__(self, identifier: str) -> None:
        self.identifier = identifier
        super().__init__(f"Skill '{identifier}' not found in registry.")


class SkillExecutionError(SkillError):
    """Erreur lors de l'exécution d'un skill."""

    def __init__(self, skill_key: str, detail: str) -> None:
        self.skill_key = skill_key
        self.detail = detail
        super().__init__(f"Error executing skill '{skill_key}': {detail}")


class SkillConfigurationError(SkillError):
    """Erreur de configuration d'un skill."""


# ──────────────────────────────────────────────
# Event Errors
# ──────────────────────────────────────────────


class EventError(AIEngineError):
    """Erreur liée au système d'événements."""


class EventHandlerError(EventError):
    """Erreur dans un handler d'événement."""

    def __init__(self, event_type: str, detail: str) -> None:
        self.event_type = event_type
        self.detail = detail
        super().__init__(f"Handler error for event '{event_type}': {detail}")


# ──────────────────────────────────────────────
# Dependency Errors
# ──────────────────────────────────────────────


class MissingDependencyError(AIEngineError):
    """Dépendance optionnelle manquante."""

    def __init__(self, package: str, extra: str) -> None:
        self.package = package
        self.extra = extra
        super().__init__(
            f"Package '{package}' is required for this feature. "
            f"Install it with: pip install ai-engine[{extra}]"
        )
