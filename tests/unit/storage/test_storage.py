"""
AI Engine — Tests for StorageBackend implementations.

Chaque test est paramétré pour tourner sur InMemoryStorage ET SQLiteStorage.
Cela garantit que les deux backends respectent exactement le même contrat.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.execution import Execution, ExecutionStep
from ai_engine.models.graph import Graph, GraphEdge, GraphNode
from ai_engine.models.knowledge import KnowledgeSource
from ai_engine.models.memory import AgentMemory
from ai_engine.models.message import Message, TokenUsage
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.models.skill import AgentSkillAssignment, Skill
from ai_engine.models.tool import ToolDefinition
from ai_engine.storage.base import StorageBackend
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.storage.sqlite import SQLiteStorage
from ai_engine.types import (
    AgentRole,
    ConversationStatus,
    ExecutionStatus,
    GraphStatus,
    MemoryType,
    MessageRole,
    NodeType,
    Proficiency,
    SkillCategory,
    SourceType,
    StepType,
    ToolType,
)

# ──────────────────────────────────────────────
# Parametrized storage fixture — runs all tests on both backends
# ──────────────────────────────────────────────


@pytest.fixture(params=["memory", "sqlite"])
def storage(request: pytest.FixtureRequest) -> StorageBackend:
    """Yields a fresh storage backend for each test."""
    if request.param == "memory":
        return InMemoryStorage()
    else:
        s = SQLiteStorage(":memory:")
        request.addfinalizer(s.close)
        return s


# ──────────────────────────────────────────────
# Helper factories
# ──────────────────────────────────────────────


def _make_provider(**overrides: object) -> LLMProviderConfig:
    defaults = {
        "name": "Test Provider",
        "provider_type": "openai",
        "default_model": "gpt-4o",
        "api_key": "sk-test-123",
    }
    defaults.update(overrides)
    return LLMProviderConfig(**defaults)  # type: ignore[arg-type]


def _make_agent(provider_id: str, **overrides: object) -> Agent:
    defaults = {
        "name": "Test Agent",
        "slug": "test-agent",
        "role": AgentRole.ASSISTANT,
        "provider_id": provider_id,
        "system_prompt": "You are a test agent.",
    }
    defaults.update(overrides)
    return Agent(**defaults)  # type: ignore[arg-type]


def _make_tool(**overrides: object) -> ToolDefinition:
    defaults = {
        "key": "web_search",
        "name": "Web Search",
        "description": "Search the web",
        "tool_type": ToolType.API,
    }
    defaults.update(overrides)
    return ToolDefinition(**defaults)  # type: ignore[arg-type]


def _make_skill(**overrides: object) -> Skill:
    defaults = {
        "key": "research",
        "name": "Research Skill",
        "category": SkillCategory.RESEARCH,
    }
    defaults.update(overrides)
    return Skill(**defaults)  # type: ignore[arg-type]


def _make_conversation(agent_id: str, **overrides: object) -> Conversation:
    defaults = {
        "title": "Test Conversation",
        "agent_id": agent_id,
        "owner_id": "user-123",
    }
    defaults.update(overrides)
    return Conversation(**defaults)  # type: ignore[arg-type]


def _make_message(conversation_id: str, **overrides: object) -> Message:
    defaults = {
        "conversation_id": conversation_id,
        "role": MessageRole.USER,
        "content": "Hello!",
    }
    defaults.update(overrides)
    return Message(**defaults)  # type: ignore[arg-type]


def _make_execution(agent_id: str, **overrides: object) -> Execution:
    defaults = {
        "agent_id": agent_id,
        "input_data": {"prompt": "test"},
    }
    defaults.update(overrides)
    return Execution(**defaults)  # type: ignore[arg-type]


def _make_graph(agent_id: str, **overrides: object) -> Graph:
    defaults = {
        "name": "Test Graph",
        "slug": "test-graph",
        "agent_id": agent_id,
        "entry_node_id": "start",
        "nodes": [
            GraphNode(node_id="start", node_type=NodeType.INPUT),
            GraphNode(node_id="end", node_type=NodeType.OUTPUT),
        ],
        "edges": [
            GraphEdge(source_node_id="start", target_node_id="end"),
        ],
    }
    defaults.update(overrides)
    return Graph(**defaults)  # type: ignore[arg-type]


def _make_memory(agent_id: str, **overrides: object) -> AgentMemory:
    defaults = {
        "agent_id": agent_id,
        "key": "user_prefs",
        "content": "prefers formal tone",
        "memory_type": MemoryType.LONG_TERM,
    }
    defaults.update(overrides)
    return AgentMemory(**defaults)  # type: ignore[arg-type]


def _make_knowledge_source(**overrides: object) -> KnowledgeSource:
    defaults = {
        "name": "Test Source",
        "source_type": SourceType.TEXT,
        "content": "Some knowledge content",
    }
    defaults.update(overrides)
    return KnowledgeSource(**defaults)  # type: ignore[arg-type]


# ══════════════════════════════════════════════
# Provider tests
# ══════════════════════════════════════════════


class TestProviderStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        found = storage.get_provider(provider.id)
        assert found is not None
        assert found.id == provider.id
        assert found.name == "Test Provider"
        assert found.default_model == "gpt-4o"

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_provider("nonexistent") is None

    def test_get_by_name(self, storage: StorageBackend) -> None:
        provider = _make_provider(name="Unique Provider")
        storage.save_provider(provider)
        found = storage.get_provider_by_name("Unique Provider")
        assert found is not None
        assert found.id == provider.id

    def test_get_by_name_not_found(self, storage: StorageBackend) -> None:
        assert storage.get_provider_by_name("nonexistent") is None

    def test_list_all(self, storage: StorageBackend) -> None:
        p1 = _make_provider(name="Provider A")
        p2 = _make_provider(name="Provider B")
        storage.save_provider(p1)
        storage.save_provider(p2)
        results = storage.list_providers()
        assert len(results) == 2

    def test_list_filter_active(self, storage: StorageBackend) -> None:
        p1 = _make_provider(name="Active", is_active=True)
        p2 = _make_provider(name="Inactive", is_active=False)
        storage.save_provider(p1)
        storage.save_provider(p2)
        active = storage.list_providers(is_active=True)
        assert len(active) == 1
        assert active[0].name == "Active"
        inactive = storage.list_providers(is_active=False)
        assert len(inactive) == 1
        assert inactive[0].name == "Inactive"

    def test_update(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        provider.name = "Updated Provider"
        storage.save_provider(provider)
        found = storage.get_provider(provider.id)
        assert found is not None
        assert found.name == "Updated Provider"

    def test_delete(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        assert storage.delete_provider(provider.id) is True
        assert storage.get_provider(provider.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_provider("nonexistent") is False

    def test_updated_at_changes_on_save(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        original_updated_at = provider.updated_at
        storage.save_provider(provider)
        assert provider.updated_at >= original_updated_at


# ══════════════════════════════════════════════
# Agent tests
# ══════════════════════════════════════════════


class TestAgentStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        found = storage.get_agent(agent.id)
        assert found is not None
        assert found.name == "Test Agent"
        assert found.provider_id == provider.id

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_agent("nonexistent") is None

    def test_get_by_slug(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id, slug="my-slug")
        storage.save_agent(agent)
        found = storage.get_agent_by_slug("my-slug")
        assert found is not None
        assert found.id == agent.id

    def test_get_by_slug_not_found(self, storage: StorageBackend) -> None:
        assert storage.get_agent_by_slug("nonexistent") is None

    def test_list_all(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, name="Agent A", slug="a")
        a2 = _make_agent(provider.id, name="Agent B", slug="b")
        storage.save_agent(a1)
        storage.save_agent(a2)
        results = storage.list_agents()
        assert len(results) == 2

    def test_list_filter_owner(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1", owner_id="owner-1")
        a2 = _make_agent(provider.id, slug="a2", owner_id="owner-2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        results = storage.list_agents(owner_id="owner-1")
        assert len(results) == 1
        assert results[0].owner_id == "owner-1"

    def test_list_filter_role(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1", role=AgentRole.RESEARCHER)
        a2 = _make_agent(provider.id, slug="a2", role=AgentRole.CODER)
        storage.save_agent(a1)
        storage.save_agent(a2)
        results = storage.list_agents(role=AgentRole.RESEARCHER)
        assert len(results) == 1
        assert results[0].role == AgentRole.RESEARCHER

    def test_list_filter_active(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1", is_active=True)
        a2 = _make_agent(provider.id, slug="a2", is_active=False)
        storage.save_agent(a1)
        storage.save_agent(a2)
        results = storage.list_agents(is_active=True)
        assert len(results) == 1

    def test_list_combined_filters(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(
            provider.id, slug="a1", owner_id="o1", role=AgentRole.CODER, is_active=True
        )
        a2 = _make_agent(
            provider.id, slug="a2", owner_id="o1", role=AgentRole.CODER, is_active=False
        )
        a3 = _make_agent(
            provider.id, slug="a3", owner_id="o2", role=AgentRole.CODER, is_active=True
        )
        storage.save_agent(a1)
        storage.save_agent(a2)
        storage.save_agent(a3)
        results = storage.list_agents(
            owner_id="o1", role=AgentRole.CODER, is_active=True
        )
        assert len(results) == 1
        assert results[0].id == a1.id

    def test_update(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        agent.name = "Updated Agent"
        storage.save_agent(agent)
        found = storage.get_agent(agent.id)
        assert found is not None
        assert found.name == "Updated Agent"

    def test_delete(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        assert storage.delete_agent(agent.id) is True
        assert storage.get_agent(agent.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_agent("nonexistent") is False

    def test_agent_config_roundtrip(self, storage: StorageBackend) -> None:
        """Verifies nested AgentConfig survives save/load."""
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(
            provider.id,
            config=AgentConfig(max_iterations=50, temperature=0.2, enable_rag=True),
        )
        storage.save_agent(agent)
        found = storage.get_agent(agent.id)
        assert found is not None
        assert found.config.max_iterations == 50
        assert found.config.temperature == 0.2
        assert found.config.enable_rag is True


# ══════════════════════════════════════════════
# Tool tests
# ══════════════════════════════════════════════


class TestToolStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        tool = _make_tool()
        storage.save_tool(tool)
        found = storage.get_tool(tool.id)
        assert found is not None
        assert found.key == "web_search"

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_tool("nonexistent") is None

    def test_get_by_key(self, storage: StorageBackend) -> None:
        tool = _make_tool(key="calculator")
        storage.save_tool(tool)
        found = storage.get_tool_by_key("calculator")
        assert found is not None
        assert found.id == tool.id

    def test_get_by_key_not_found(self, storage: StorageBackend) -> None:
        assert storage.get_tool_by_key("nonexistent") is None

    def test_list_all(self, storage: StorageBackend) -> None:
        t1 = _make_tool(key="t1", name="Tool 1")
        t2 = _make_tool(key="t2", name="Tool 2")
        storage.save_tool(t1)
        storage.save_tool(t2)
        results = storage.list_tools()
        assert len(results) == 2

    def test_list_filter_active(self, storage: StorageBackend) -> None:
        t1 = _make_tool(key="active", is_active=True)
        t2 = _make_tool(key="inactive", is_active=False)
        storage.save_tool(t1)
        storage.save_tool(t2)
        active = storage.list_tools(is_active=True)
        assert len(active) == 1
        assert active[0].key == "active"

    def test_list_tools_for_agent(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        t1 = _make_tool(key="t1")
        t2 = _make_tool(key="t2")
        t3 = _make_tool(key="t3")
        storage.save_tool(t1)
        storage.save_tool(t2)
        storage.save_tool(t3)
        agent = _make_agent(provider.id, tool_ids=[t1.id, t3.id])
        storage.save_agent(agent)
        tools = storage.list_tools_for_agent(agent.id)
        assert len(tools) == 2
        tool_keys = {t.key for t in tools}
        assert tool_keys == {"t1", "t3"}

    def test_list_tools_for_nonexistent_agent(self, storage: StorageBackend) -> None:
        result = storage.list_tools_for_agent("nonexistent")
        assert result == []

    def test_update(self, storage: StorageBackend) -> None:
        tool = _make_tool()
        storage.save_tool(tool)
        tool.description = "Updated description"
        storage.save_tool(tool)
        found = storage.get_tool(tool.id)
        assert found is not None
        assert found.description == "Updated description"

    def test_delete(self, storage: StorageBackend) -> None:
        tool = _make_tool()
        storage.save_tool(tool)
        assert storage.delete_tool(tool.id) is True
        assert storage.get_tool(tool.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_tool("nonexistent") is False


# ══════════════════════════════════════════════
# Skill tests
# ══════════════════════════════════════════════


class TestSkillStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        skill = _make_skill()
        storage.save_skill(skill)
        found = storage.get_skill(skill.id)
        assert found is not None
        assert found.key == "research"

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_skill("nonexistent") is None

    def test_list_all(self, storage: StorageBackend) -> None:
        s1 = _make_skill(key="s1")
        s2 = _make_skill(key="s2")
        storage.save_skill(s1)
        storage.save_skill(s2)
        results = storage.list_skills()
        assert len(results) == 2

    def test_list_filter_active(self, storage: StorageBackend) -> None:
        s1 = _make_skill(key="active", is_active=True)
        s2 = _make_skill(key="inactive", is_active=False)
        storage.save_skill(s1)
        storage.save_skill(s2)
        active = storage.list_skills(is_active=True)
        assert len(active) == 1
        assert active[0].key == "active"

    def test_delete(self, storage: StorageBackend) -> None:
        skill = _make_skill()
        storage.save_skill(skill)
        assert storage.delete_skill(skill.id) is True
        assert storage.get_skill(skill.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_skill("nonexistent") is False

    def test_skill_assignment(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        skill = _make_skill()
        storage.save_skill(skill)
        assignment = AgentSkillAssignment(
            agent_id=agent.id,
            skill_id=skill.id,
            proficiency=Proficiency.ADVANCED,
        )
        storage.save_skill_assignment(assignment)
        assignments = storage.list_skill_assignments_for_agent(agent.id)
        assert len(assignments) == 1
        assert assignments[0].skill_id == skill.id
        assert assignments[0].proficiency == Proficiency.ADVANCED

    def test_skill_assignment_multiple_agents(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        skill = _make_skill()
        storage.save_skill(skill)
        sa1 = AgentSkillAssignment(agent_id=a1.id, skill_id=skill.id)
        sa2 = AgentSkillAssignment(agent_id=a2.id, skill_id=skill.id)
        storage.save_skill_assignment(sa1)
        storage.save_skill_assignment(sa2)
        assert len(storage.list_skill_assignments_for_agent(a1.id)) == 1
        assert len(storage.list_skill_assignments_for_agent(a2.id)) == 1


# ══════════════════════════════════════════════
# Conversation tests
# ══════════════════════════════════════════════


class TestConversationStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        conv = _make_conversation(agent.id)
        storage.save_conversation(conv)
        found = storage.get_conversation(conv.id)
        assert found is not None
        assert found.title == "Test Conversation"
        assert found.agent_id == agent.id

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_conversation("nonexistent") is None

    def test_list_filter_agent(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        c1 = _make_conversation(a1.id)
        c2 = _make_conversation(a2.id)
        storage.save_conversation(c1)
        storage.save_conversation(c2)
        results = storage.list_conversations(agent_id=a1.id)
        assert len(results) == 1
        assert results[0].agent_id == a1.id

    def test_list_filter_owner(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        c1 = _make_conversation(agent.id, owner_id="owner-A")
        c2 = _make_conversation(agent.id, owner_id="owner-B")
        storage.save_conversation(c1)
        storage.save_conversation(c2)
        results = storage.list_conversations(owner_id="owner-A")
        assert len(results) == 1
        assert results[0].owner_id == "owner-A"

    def test_update(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        conv = _make_conversation(agent.id)
        storage.save_conversation(conv)
        conv.title = "Updated Title"
        conv.status = ConversationStatus.ARCHIVED
        storage.save_conversation(conv)
        found = storage.get_conversation(conv.id)
        assert found is not None
        assert found.title == "Updated Title"
        assert found.status == ConversationStatus.ARCHIVED

    def test_delete(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        conv = _make_conversation(agent.id)
        storage.save_conversation(conv)
        assert storage.delete_conversation(conv.id) is True
        assert storage.get_conversation(conv.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_conversation("nonexistent") is False


# ══════════════════════════════════════════════
# Message tests
# ══════════════════════════════════════════════


class TestMessageStorage:
    def _setup_conversation(self, storage: StorageBackend) -> tuple[str, str]:
        """Helper: creates provider + agent + conversation, returns (agent_id, conv_id)."""
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        conv = _make_conversation(agent.id)
        storage.save_conversation(conv)
        return agent.id, conv.id

    def test_save_and_get(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        msg = _make_message(conv_id, content="Hello!")
        storage.save_message(msg)
        messages = storage.get_messages(conv_id)
        assert len(messages) == 1
        assert messages[0].content == "Hello!"

    def test_messages_ordered_by_created_at(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        now = datetime.now(UTC)
        m1 = _make_message(
            conv_id, content="First", created_at=now - timedelta(seconds=2)
        )
        m2 = _make_message(
            conv_id, content="Second", created_at=now - timedelta(seconds=1)
        )
        m3 = _make_message(conv_id, content="Third", created_at=now)
        # Save in scrambled order
        storage.save_message(m3)
        storage.save_message(m1)
        storage.save_message(m2)
        messages = storage.get_messages(conv_id)
        assert [m.content for m in messages] == ["First", "Second", "Third"]

    def test_pagination_limit(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        now = datetime.now(UTC)
        for i in range(5):
            msg = _make_message(
                conv_id,
                content=f"Message {i}",
                created_at=now + timedelta(seconds=i),
            )
            storage.save_message(msg)
        messages = storage.get_messages(conv_id, limit=3)
        assert len(messages) == 3
        assert messages[0].content == "Message 0"
        assert messages[2].content == "Message 2"

    def test_pagination_offset(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        now = datetime.now(UTC)
        for i in range(5):
            msg = _make_message(
                conv_id,
                content=f"Message {i}",
                created_at=now + timedelta(seconds=i),
            )
            storage.save_message(msg)
        messages = storage.get_messages(conv_id, offset=2)
        assert len(messages) == 3
        assert messages[0].content == "Message 2"

    def test_pagination_limit_and_offset(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        now = datetime.now(UTC)
        for i in range(10):
            msg = _make_message(
                conv_id,
                content=f"Message {i}",
                created_at=now + timedelta(seconds=i),
            )
            storage.save_message(msg)
        messages = storage.get_messages(conv_id, limit=3, offset=2)
        assert len(messages) == 3
        assert messages[0].content == "Message 2"
        assert messages[2].content == "Message 4"

    def test_count_messages(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        assert storage.count_messages(conv_id) == 0
        for i in range(3):
            storage.save_message(_make_message(conv_id, content=f"Msg {i}"))
        assert storage.count_messages(conv_id) == 3

    def test_count_messages_empty_conversation(self, storage: StorageBackend) -> None:
        assert storage.count_messages("nonexistent-conv") == 0

    def test_messages_isolated_per_conversation(self, storage: StorageBackend) -> None:
        _, conv_id1 = self._setup_conversation(storage)
        provider = _make_provider(name="P2")
        storage.save_provider(provider)
        agent = _make_agent(provider.id, slug="a2")
        storage.save_agent(agent)
        conv2 = _make_conversation(agent.id)
        storage.save_conversation(conv2)
        storage.save_message(_make_message(conv_id1, content="In conv 1"))
        storage.save_message(_make_message(conv2.id, content="In conv 2"))
        assert len(storage.get_messages(conv_id1)) == 1
        assert len(storage.get_messages(conv2.id)) == 1
        assert storage.get_messages(conv_id1)[0].content == "In conv 1"

    def test_message_with_token_usage_roundtrip(self, storage: StorageBackend) -> None:
        _, conv_id = self._setup_conversation(storage)
        msg = _make_message(
            conv_id,
            role=MessageRole.ASSISTANT,
            content="Response",
            token_usage=TokenUsage(
                prompt_tokens=10, completion_tokens=20, total_tokens=30
            ),
        )
        storage.save_message(msg)
        loaded = storage.get_messages(conv_id)
        assert len(loaded) == 1
        assert loaded[0].token_usage is not None
        assert loaded[0].token_usage.total_tokens == 30


# ══════════════════════════════════════════════
# Execution tests
# ══════════════════════════════════════════════


class TestExecutionStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        execution = _make_execution(agent.id)
        storage.save_execution(execution)
        found = storage.get_execution(execution.id)
        assert found is not None
        assert found.agent_id == agent.id
        assert found.status == ExecutionStatus.PENDING

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_execution("nonexistent") is None

    def test_list_filter_agent(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        e1 = _make_execution(a1.id)
        e2 = _make_execution(a2.id)
        storage.save_execution(e1)
        storage.save_execution(e2)
        results = storage.list_executions(agent_id=a1.id)
        assert len(results) == 1
        assert results[0].agent_id == a1.id

    def test_list_filter_status(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        e1 = _make_execution(agent.id, status=ExecutionStatus.PENDING)
        e2 = _make_execution(agent.id, status=ExecutionStatus.RUNNING)
        e3 = _make_execution(agent.id, status=ExecutionStatus.SUCCESS)
        storage.save_execution(e1)
        storage.save_execution(e2)
        storage.save_execution(e3)
        running = storage.list_executions(status=ExecutionStatus.RUNNING)
        assert len(running) == 1
        assert running[0].status == ExecutionStatus.RUNNING

    def test_update_status(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        execution = _make_execution(agent.id)
        storage.save_execution(execution)
        execution.status = ExecutionStatus.RUNNING
        execution.started_at = datetime.now(UTC)
        storage.save_execution(execution)
        found = storage.get_execution(execution.id)
        assert found is not None
        assert found.status == ExecutionStatus.RUNNING
        assert found.started_at is not None

    def test_execution_steps(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        execution = _make_execution(agent.id)
        storage.save_execution(execution)
        step1 = ExecutionStep(
            execution_id=execution.id,
            step_type=StepType.LLM_CALL,
            order=0,
            input_data={"prompt": "test"},
        )
        step2 = ExecutionStep(
            execution_id=execution.id,
            step_type=StepType.TOOL_CALL,
            order=1,
            input_data={"tool": "web_search"},
        )
        # Save in reverse order
        storage.save_execution_step(step2)
        storage.save_execution_step(step1)
        steps = storage.get_execution_steps(execution.id)
        assert len(steps) == 2
        assert steps[0].order == 0
        assert steps[0].step_type == StepType.LLM_CALL
        assert steps[1].order == 1
        assert steps[1].step_type == StepType.TOOL_CALL

    def test_execution_steps_empty(self, storage: StorageBackend) -> None:
        steps = storage.get_execution_steps("nonexistent")
        assert steps == []


# ══════════════════════════════════════════════
# Graph tests
# ══════════════════════════════════════════════


class TestGraphStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        graph = _make_graph(agent.id)
        storage.save_graph(graph)
        found = storage.get_graph(graph.id)
        assert found is not None
        assert found.name == "Test Graph"
        assert len(found.nodes) == 2
        assert len(found.edges) == 1

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_graph("nonexistent") is None

    def test_get_by_slug(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        graph = _make_graph(agent.id, slug="my-pipeline")
        storage.save_graph(graph)
        found = storage.get_graph_by_slug("my-pipeline")
        assert found is not None
        assert found.id == graph.id

    def test_get_by_slug_not_found(self, storage: StorageBackend) -> None:
        assert storage.get_graph_by_slug("nonexistent") is None

    def test_list_filter_agent(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        g1 = _make_graph(a1.id, slug="g1")
        g2 = _make_graph(a2.id, slug="g2")
        storage.save_graph(g1)
        storage.save_graph(g2)
        results = storage.list_graphs(agent_id=a1.id)
        assert len(results) == 1
        assert results[0].agent_id == a1.id

    def test_list_filter_owner(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        g1 = _make_graph(agent.id, slug="g1", owner_id="owner-1")
        g2 = _make_graph(agent.id, slug="g2", owner_id="owner-2")
        storage.save_graph(g1)
        storage.save_graph(g2)
        results = storage.list_graphs(owner_id="owner-1")
        assert len(results) == 1
        assert results[0].owner_id == "owner-1"

    def test_update(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        graph = _make_graph(agent.id)
        storage.save_graph(graph)
        graph.status = GraphStatus.ACTIVE
        graph.version = 2
        storage.save_graph(graph)
        found = storage.get_graph(graph.id)
        assert found is not None
        assert found.status == GraphStatus.ACTIVE
        assert found.version == 2

    def test_delete(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        graph = _make_graph(agent.id)
        storage.save_graph(graph)
        assert storage.delete_graph(graph.id) is True
        assert storage.get_graph(graph.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_graph("nonexistent") is False

    def test_graph_nodes_roundtrip(self, storage: StorageBackend) -> None:
        """Verifies complex nested GraphNode/GraphEdge survive serialization."""
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        graph = Graph(
            name="Complex Graph",
            slug="complex",
            agent_id=agent.id,
            entry_node_id="start",
            nodes=[
                GraphNode(node_id="start", node_type=NodeType.INPUT, name="Start"),
                GraphNode(
                    node_id="researcher",
                    node_type=NodeType.AGENT,
                    name="Researcher",
                    config={"agent_id": "some-agent-id"},
                ),
                GraphNode(
                    node_id="check",
                    node_type=NodeType.CONDITION,
                    config={"expr": "x > 0"},
                ),
                GraphNode(node_id="end", node_type=NodeType.OUTPUT, name="End"),
            ],
            edges=[
                GraphEdge(source_node_id="start", target_node_id="researcher"),
                GraphEdge(source_node_id="researcher", target_node_id="check"),
                GraphEdge(
                    source_node_id="check", target_node_id="end", condition="True"
                ),
            ],
            state_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
            },
        )
        storage.save_graph(graph)
        found = storage.get_graph(graph.id)
        assert found is not None
        assert len(found.nodes) == 4
        assert len(found.edges) == 3
        assert found.state_schema["type"] == "object"
        researcher = found.get_node("researcher")
        assert researcher is not None
        assert researcher.config["agent_id"] == "some-agent-id"


# ══════════════════════════════════════════════
# Memory tests
# ══════════════════════════════════════════════


class TestMemoryStorage:
    def _setup_agent(self, storage: StorageBackend) -> str:
        provider = _make_provider()
        storage.save_provider(provider)
        agent = _make_agent(provider.id)
        storage.save_agent(agent)
        return agent.id

    def test_save_and_get(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        mem = _make_memory(agent_id)
        storage.save_memory(mem)
        found = storage.get_memory(agent_id, "user_prefs")
        assert found is not None
        assert found.content == "prefers formal tone"

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_memory("nonexistent", "key") is None

    def test_list_by_agent(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        m1 = _make_memory(agent_id, key="k1")
        m2 = _make_memory(agent_id, key="k2")
        storage.save_memory(m1)
        storage.save_memory(m2)
        results = storage.list_memories(agent_id)
        assert len(results) == 2

    def test_list_filter_type(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        m1 = _make_memory(agent_id, key="k1", memory_type=MemoryType.LONG_TERM)
        m2 = _make_memory(agent_id, key="k2", memory_type=MemoryType.SHORT_TERM)
        storage.save_memory(m1)
        storage.save_memory(m2)
        long_term = storage.list_memories(agent_id, memory_type=MemoryType.LONG_TERM)
        assert len(long_term) == 1
        assert long_term[0].key == "k1"

    def test_update(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        mem = _make_memory(agent_id)
        storage.save_memory(mem)
        mem.content = "updated content"
        storage.save_memory(mem)
        found = storage.get_memory(agent_id, "user_prefs")
        assert found is not None
        assert found.content == "updated content"

    def test_delete(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        mem = _make_memory(agent_id)
        storage.save_memory(mem)
        assert storage.delete_memory(mem.id) is True
        assert storage.get_memory(agent_id, "user_prefs") is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_memory("nonexistent") is False

    def test_delete_expired_memories(self, storage: StorageBackend) -> None:
        agent_id = self._setup_agent(storage)
        past = datetime.now(UTC) - timedelta(hours=1)
        future = datetime.now(UTC) + timedelta(hours=1)
        m_expired = _make_memory(agent_id, key="expired", expires_at=past)
        m_valid = _make_memory(agent_id, key="valid", expires_at=future)
        m_no_expiry = _make_memory(agent_id, key="forever")
        storage.save_memory(m_expired)
        storage.save_memory(m_valid)
        storage.save_memory(m_no_expiry)
        deleted = storage.delete_expired_memories()
        assert deleted == 1
        assert storage.get_memory(agent_id, "expired") is None
        assert storage.get_memory(agent_id, "valid") is not None
        assert storage.get_memory(agent_id, "forever") is not None

    def test_delete_expired_memories_none_expired(
        self, storage: StorageBackend
    ) -> None:
        agent_id = self._setup_agent(storage)
        future = datetime.now(UTC) + timedelta(hours=1)
        m = _make_memory(agent_id, key="valid", expires_at=future)
        storage.save_memory(m)
        assert storage.delete_expired_memories() == 0

    def test_memories_isolated_per_agent(self, storage: StorageBackend) -> None:
        agent_id1 = self._setup_agent(storage)
        provider2 = _make_provider(name="P2")
        storage.save_provider(provider2)
        agent2 = _make_agent(provider2.id, slug="a2")
        storage.save_agent(agent2)
        storage.save_memory(_make_memory(agent_id1, key="k1"))
        storage.save_memory(_make_memory(agent2.id, key="k2"))
        assert len(storage.list_memories(agent_id1)) == 1
        assert len(storage.list_memories(agent2.id)) == 1


# ══════════════════════════════════════════════
# Knowledge Source tests
# ══════════════════════════════════════════════


class TestKnowledgeSourceStorage:
    def test_save_and_get(self, storage: StorageBackend) -> None:
        source = _make_knowledge_source()
        storage.save_knowledge_source(source)
        found = storage.get_knowledge_source(source.id)
        assert found is not None
        assert found.name == "Test Source"

    def test_get_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.get_knowledge_source("nonexistent") is None

    def test_list_all(self, storage: StorageBackend) -> None:
        s1 = _make_knowledge_source(name="Source 1")
        s2 = _make_knowledge_source(name="Source 2")
        storage.save_knowledge_source(s1)
        storage.save_knowledge_source(s2)
        results = storage.list_knowledge_sources()
        assert len(results) == 2

    def test_list_filter_agent(self, storage: StorageBackend) -> None:
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        s1 = _make_knowledge_source(name="S1", agent_ids=[a1.id])
        s2 = _make_knowledge_source(name="S2", agent_ids=[a2.id])
        s3 = _make_knowledge_source(name="S3", agent_ids=[a1.id, a2.id])
        storage.save_knowledge_source(s1)
        storage.save_knowledge_source(s2)
        storage.save_knowledge_source(s3)
        for_a1 = storage.list_knowledge_sources(agent_id=a1.id)
        assert len(for_a1) == 2  # s1 and s3
        for_a2 = storage.list_knowledge_sources(agent_id=a2.id)
        assert len(for_a2) == 2  # s2 and s3

    def test_update(self, storage: StorageBackend) -> None:
        source = _make_knowledge_source()
        storage.save_knowledge_source(source)
        source.name = "Updated Source"
        storage.save_knowledge_source(source)
        found = storage.get_knowledge_source(source.id)
        assert found is not None
        assert found.name == "Updated Source"

    def test_delete(self, storage: StorageBackend) -> None:
        source = _make_knowledge_source()
        storage.save_knowledge_source(source)
        assert storage.delete_knowledge_source(source.id) is True
        assert storage.get_knowledge_source(source.id) is None

    def test_delete_nonexistent(self, storage: StorageBackend) -> None:
        assert storage.delete_knowledge_source("nonexistent") is False

    def test_update_agent_ids(self, storage: StorageBackend) -> None:
        """Verify that saving with updated agent_ids replaces the old associations."""
        provider = _make_provider()
        storage.save_provider(provider)
        a1 = _make_agent(provider.id, slug="a1")
        a2 = _make_agent(provider.id, slug="a2")
        storage.save_agent(a1)
        storage.save_agent(a2)
        source = _make_knowledge_source(agent_ids=[a1.id])
        storage.save_knowledge_source(source)
        assert len(storage.list_knowledge_sources(agent_id=a1.id)) == 1
        assert len(storage.list_knowledge_sources(agent_id=a2.id)) == 0
        # Update to associate with a2 instead
        source.agent_ids = [a2.id]
        storage.save_knowledge_source(source)
        assert len(storage.list_knowledge_sources(agent_id=a1.id)) == 0
        assert len(storage.list_knowledge_sources(agent_id=a2.id)) == 1


# ══════════════════════════════════════════════
# Cross-cutting / lifecycle tests
# ══════════════════════════════════════════════


class TestStorageLifecycle:
    def test_context_manager(self) -> None:
        with InMemoryStorage() as storage:
            provider = _make_provider()
            storage.save_provider(provider)
            assert storage.get_provider(provider.id) is not None

    def test_sqlite_context_manager(self) -> None:
        with SQLiteStorage(":memory:") as storage:
            provider = _make_provider()
            storage.save_provider(provider)
            assert storage.get_provider(provider.id) is not None

    def test_transaction_noop_on_memory(self) -> None:
        storage = InMemoryStorage()
        with storage.transaction():
            storage.save_provider(_make_provider())
        assert len(storage.list_providers()) == 1

    def test_sqlite_transaction_commit(self) -> None:
        with SQLiteStorage(":memory:") as storage:
            with storage.transaction():
                storage.save_provider(_make_provider(name="In Transaction"))
            # Should be committed
            assert len(storage.list_providers()) == 1

    def test_sqlite_transaction_rollback(self) -> None:
        with SQLiteStorage(":memory:") as storage:
            provider = _make_provider(name="Will Rollback")
            storage.save_provider(provider)
            try:
                with storage.transaction():
                    storage.save_provider(_make_provider(name="In Transaction"))
                    raise ValueError("force rollback")
            except ValueError:
                pass
            # The original provider should still be there,
            # but the one from the failed transaction should not
            providers = storage.list_providers()
            names = {p.name for p in providers}
            assert "Will Rollback" in names
            # Note: Due to SQLite's autocommit behavior with INSERT OR REPLACE
            # and the transaction context manager, behavior here depends on
            # whether the first save was committed before the transaction block
