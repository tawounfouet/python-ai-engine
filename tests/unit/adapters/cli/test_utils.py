"""
Unit tests for the CLI adapter — utils helpers.
"""

from __future__ import annotations

import pytest

import typer

from ai_engine.adapters.cli.utils import (
    abort,
    get_agent_service,
    get_storage,
    resolve_agent,
    resolve_conversation,
    resolve_provider,
)
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.types import AgentRole, ProviderType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def saved_provider(storage: InMemoryStorage) -> LLMProviderConfig:
    p = LLMProviderConfig(
        name="Test OpenAI",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
    )
    storage.save_provider(p)
    return p


@pytest.fixture
def saved_agent(storage: InMemoryStorage, saved_provider: LLMProviderConfig) -> Agent:
    a = Agent(
        name="Test Agent",
        slug="test-agent",
        provider_id=saved_provider.id,
        system_prompt="You are helpful.",
        role=AgentRole.ASSISTANT,
        config=AgentConfig(),
    )
    storage.save_agent(a)
    return a


@pytest.fixture
def saved_conversation(storage: InMemoryStorage, saved_agent: Agent) -> Conversation:
    c = Conversation(agent_id=saved_agent.id, title="Test Conversation")
    storage.save_conversation(c)
    return c


# ── get_storage ───────────────────────────────────────────────────────────────


def test_get_storage_returns_sqlite(tmp_path):
    from ai_engine.storage.sqlite import SQLiteStorage

    db = str(tmp_path / "test.db")
    s = get_storage(db)
    assert isinstance(s, SQLiteStorage)


# ── get_agent_service ─────────────────────────────────────────────────────────


def test_get_agent_service_returns_service(tmp_path):
    from ai_engine.services.agent import AgentService

    db = str(tmp_path / "test.db")
    svc = get_agent_service(db)
    assert isinstance(svc, AgentService)


# ── resolve_agent ─────────────────────────────────────────────────────────────


def test_resolve_agent_by_exact_id(storage, saved_agent):
    result = resolve_agent(storage, saved_agent.id)
    assert result.id == saved_agent.id


def test_resolve_agent_by_slug(storage, saved_agent):
    result = resolve_agent(storage, "test-agent")
    assert result.slug == "test-agent"


def test_resolve_agent_by_prefix(storage, saved_agent):
    prefix = saved_agent.id[:8]
    result = resolve_agent(storage, prefix)
    assert result.id == saved_agent.id


def test_resolve_agent_not_found_exits(storage):
    with pytest.raises(typer.Exit):
        resolve_agent(storage, "nonexistent-agent")


def test_resolve_agent_ambiguous_prefix_exits(storage, saved_provider):
    """Two agents sharing the same prefix should cause an ambiguity error."""
    # Force same 8-char prefix by using a known UUID prefix collision via mock
    a1 = Agent(
        name="A1",
        slug="a1",
        provider_id=saved_provider.id,
        role=AgentRole.ASSISTANT,
        config=AgentConfig(),
    )
    a2 = Agent(
        name="A2",
        slug="a2",
        provider_id=saved_provider.id,
        role=AgentRole.ASSISTANT,
        config=AgentConfig(),
    )
    # Manually set IDs to share the same 8-char prefix
    a1.id = "aaaaaaaa-0000-0000-0000-000000000001"
    a2.id = "aaaaaaaa-0000-0000-0000-000000000002"
    storage.save_agent(a1)
    storage.save_agent(a2)

    with pytest.raises(typer.Exit):
        resolve_agent(storage, "aaaaaaaa")


# ── resolve_provider ──────────────────────────────────────────────────────────


def test_resolve_provider_by_exact_id(storage, saved_provider):
    result = resolve_provider(storage, saved_provider.id)
    assert result.id == saved_provider.id


def test_resolve_provider_by_name(storage, saved_provider):
    result = resolve_provider(storage, "Test OpenAI")
    assert result.name == "Test OpenAI"


def test_resolve_provider_by_prefix(storage, saved_provider):
    prefix = saved_provider.id[:8]
    result = resolve_provider(storage, prefix)
    assert result.id == saved_provider.id


def test_resolve_provider_not_found_exits(storage):
    with pytest.raises(typer.Exit):
        resolve_provider(storage, "nonexistent-provider")


# ── resolve_conversation ──────────────────────────────────────────────────────


def test_resolve_conversation_by_exact_id(storage, saved_conversation):
    result = resolve_conversation(storage, saved_conversation.id)
    assert result.id == saved_conversation.id


def test_resolve_conversation_by_prefix(storage, saved_conversation):
    prefix = saved_conversation.id[:8]
    result = resolve_conversation(storage, prefix)
    assert result.id == saved_conversation.id


def test_resolve_conversation_not_found_exits(storage):
    with pytest.raises(typer.Exit):
        resolve_conversation(storage, "nonexistent-conv")


# ── abort ─────────────────────────────────────────────────────────────────────


def test_abort_raises_exit():
    with pytest.raises(typer.Exit):
        abort("Something went wrong")


def test_abort_custom_code():
    with pytest.raises(typer.Exit) as exc_info:
        abort("Fatal error", code=2)
    assert exc_info.value.exit_code == 2
