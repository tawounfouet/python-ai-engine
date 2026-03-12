"""
AI Engine — Types communs et Enums partagés.

Ce module centralise tous les types réutilisés à travers le package.
Aucune logique métier ici, uniquement des définitions de types.
"""

from __future__ import annotations

from enum import StrEnum

# ──────────────────────────────────────────────
# Provider Types
# ──────────────────────────────────────────────


class ProviderType(StrEnum):
    """Types de fournisseurs LLM supportés."""

    # OpenAI Family
    OPENAI = "openai"
    OPENAI_AZURE = "openai_azure"
    CODEX = "codex"

    # Anthropic Family
    ANTHROPIC = "anthropic"
    CLAUDE_CODE = "claude_code"

    # Chinese LLMs
    QWEN = "qwen"
    MOONSHOT = "moonshot"
    KIMI_CODING = "kimi_coding"
    GLM = "glm"
    MINIMAX = "minimax"
    XIAOMI = "xiaomi"

    # Gateways
    OPENROUTER = "openrouter"
    VERCEL_AI = "vercel_ai"

    # Cloud Providers
    BEDROCK = "bedrock"
    VERTEX_AI = "vertex_ai"

    # Specialized
    VENICE = "venice"
    ZAI = "zai"
    OPENCODE_ZEN = "opencode_zen"

    # Local
    OLLAMA = "ollama"
    LLAMACPP = "llamacpp"
    VLLM = "vllm"

    # Generic
    CUSTOM = "custom"


# ──────────────────────────────────────────────
# Agent Roles
# ──────────────────────────────────────────────


class AgentRole(StrEnum):
    """Rôles possibles pour un agent AI."""

    ASSISTANT = "assistant"
    RESEARCHER = "researcher"
    CODER = "coder"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    ORCHESTRATOR = "orchestrator"
    CUSTOM = "custom"


# ──────────────────────────────────────────────
# Tool Types
# ──────────────────────────────────────────────


class ToolType(StrEnum):
    """Types d'outils disponibles."""

    FUNCTION = "function"
    API = "api"
    DATABASE = "database"
    FILE = "file"
    CONNECTOR = "connector"
    CUSTOM = "custom"


# ──────────────────────────────────────────────
# Skill Categories
# ──────────────────────────────────────────────


class SkillCategory(StrEnum):
    """Catégories de compétences."""

    RESEARCH = "research"
    CODING = "coding"
    COMMUNICATION = "communication"
    DATA = "data"
    CREATIVE = "creative"
    AUTOMATION = "automation"
    CUSTOM = "custom"


class Proficiency(StrEnum):
    """Niveau de maîtrise d'un skill par un agent."""

    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


# ──────────────────────────────────────────────
# Message Roles
# ──────────────────────────────────────────────


class MessageRole(StrEnum):
    """Rôles de messages dans une conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


# ──────────────────────────────────────────────
# Conversation Status
# ──────────────────────────────────────────────


class ConversationStatus(StrEnum):
    """Statuts d'une conversation."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# ──────────────────────────────────────────────
# Graph Types
# ──────────────────────────────────────────────


class GraphStatus(StrEnum):
    """Statuts d'un graph."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class NodeType(StrEnum):
    """Types de nœuds dans un graph."""

    AGENT = "agent"
    CONDITION = "condition"
    TOOL = "tool"
    INPUT = "input"
    OUTPUT = "output"
    PARALLEL = "parallel"
    LOOP = "loop"


# ──────────────────────────────────────────────
# Execution Types
# ──────────────────────────────────────────────


class ExecutionStatus(StrEnum):
    """Statuts d'une exécution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(StrEnum):
    """Types d'étapes dans une exécution."""

    LLM_CALL = "llm_call"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DECISION = "decision"
    ERROR = "error"


# ──────────────────────────────────────────────
# Memory Types
# ──────────────────────────────────────────────


class MemoryType(StrEnum):
    """Types de mémoire pour un agent."""

    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    EPISODIC = "episodic"


# ──────────────────────────────────────────────
# Knowledge Types
# ──────────────────────────────────────────────


class SourceType(StrEnum):
    """Types de sources de connaissance."""

    DOCUMENT = "document"
    URL = "url"
    TEXT = "text"
    DATABASE = "database"
    API = "api"


class IndexStatus(StrEnum):
    """Statuts d'indexation d'une source de connaissance."""

    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"
