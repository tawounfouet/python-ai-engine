"""
AI Engine — Pure Python AI/LLM toolkit.

Package standalone pour orchestrer des agents LLM, sans dépendance à Django.
Fonctionne en scripts, notebooks, CLI, FastAPI, Lambda, Django, etc.

Usage rapide:
    from ai_engine import Agent, LLMProviderConfig, ProviderType, AgentRole

    provider = LLMProviderConfig(
        name="OpenAI GPT-4o",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key="sk-...",
    )

    agent = Agent(
        name="Research Assistant",
        role=AgentRole.RESEARCHER,
        provider_id=provider.id,
        system_prompt="Tu es un chercheur expert.",
    )
"""

from __future__ import annotations

__version__ = "0.1.0"

# ── Types & Enums ──
# ── Config ──
from ai_engine.config import Settings, get_settings

# ── Exceptions ──
from ai_engine.exceptions import (
    AgentDisabledError,
    AgentError,
    AgentNotFoundError,
    AIEngineError,
    APIKeyMissingError,
    ConversationError,
    ConversationNotFoundError,
    ExecutionError,
    ExecutionNotFoundError,
    GraphError,
    GraphNotFoundError,
    MissingDependencyError,
    ProviderError,
    ProviderNotFoundError,
    StorageConnectionError,
    StorageError,
    ToolError,
    ToolExecutionError,
    ToolNotFoundError,
    UnsupportedProviderError,
)

# ── Models ──
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.execution import Execution, ExecutionStep
from ai_engine.models.graph import Graph, GraphEdge, GraphNode
from ai_engine.models.knowledge import Chunk, Document, KnowledgeSource
from ai_engine.models.memory import AgentMemory
from ai_engine.models.message import Message, TokenUsage, ToolCall, ToolResult
from ai_engine.models.provider import (
    LLMProviderConfig,
    PricingConfig,
    ProviderCapabilities,
    ProviderSettings,
)
from ai_engine.models.skill import AgentSkillAssignment, Skill
from ai_engine.models.tool import ToolDefinition

# ── Storage ──
from ai_engine.storage.base import StorageBackend
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.storage.sqlite import SQLiteStorage

# ── Tools ──
from ai_engine.tools import ToolExecutor, ToolRegistry
from ai_engine.types import (
    AgentRole,
    ConversationStatus,
    ExecutionStatus,
    GraphStatus,
    IndexStatus,
    MemoryType,
    MessageRole,
    NodeType,
    Proficiency,
    ProviderType,
    SkillCategory,
    SourceType,
    StepType,
    ToolType,
)

__all__ = [
    # Meta
    "__version__",
    # Types & Enums
    "ProviderType",
    "AgentRole",
    "ToolType",
    "SkillCategory",
    "Proficiency",
    "MessageRole",
    "ConversationStatus",
    "GraphStatus",
    "NodeType",
    "ExecutionStatus",
    "StepType",
    "MemoryType",
    "SourceType",
    "IndexStatus",
    # Storage
    "StorageBackend",
    "InMemoryStorage",
    "SQLiteStorage",
    # Tools
    "ToolRegistry",
    "ToolExecutor",
    # Models — Provider
    "LLMProviderConfig",
    "ProviderCapabilities",
    "PricingConfig",
    "ProviderSettings",
    # Models — Agent
    "Agent",
    "AgentConfig",
    # Models — Tool
    "ToolDefinition",
    # Models — Skill
    "Skill",
    "AgentSkillAssignment",
    # Models — Conversation
    "Conversation",
    # Models — Message
    "Message",
    "ToolCall",
    "ToolResult",
    "TokenUsage",
    # Models — Graph
    "Graph",
    "GraphNode",
    "GraphEdge",
    # Models — Execution
    "Execution",
    "ExecutionStep",
    # Models — Memory
    "AgentMemory",
    # Models — Knowledge
    "KnowledgeSource",
    "Document",
    "Chunk",
    # Config
    "Settings",
    "get_settings",
    # Exceptions
    "AIEngineError",
    "ProviderError",
    "ProviderNotFoundError",
    "UnsupportedProviderError",
    "APIKeyMissingError",
    "AgentError",
    "AgentNotFoundError",
    "AgentDisabledError",
    "ConversationError",
    "ConversationNotFoundError",
    "GraphError",
    "GraphNotFoundError",
    "ExecutionError",
    "ExecutionNotFoundError",
    "ToolError",
    "ToolNotFoundError",
    "ToolExecutionError",
    "StorageError",
    "StorageConnectionError",
    "MissingDependencyError",
]
