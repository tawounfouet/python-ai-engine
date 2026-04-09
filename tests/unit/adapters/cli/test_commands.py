"""
Unit tests for the CLI commands (provider, agent, conversation, config).

Uses Typer's CliRunner so no subprocess is spawned.
Storage is always an InMemoryStorage injected via monkeypatch.
"""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from ai_engine.adapters.cli.app import app
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.types import AgentRole, ProviderType

runner = CliRunner()


# ── Shared fixtures & patch helper ───────────────────────────────────────────


@pytest.fixture
def mem_storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def populated_storage() -> InMemoryStorage:
    """InMemoryStorage pre-filled with one provider, one agent, one conversation."""
    storage = InMemoryStorage()

    p = LLMProviderConfig(
        name="OpenAI Test",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o-mini",
    )
    storage.save_provider(p)

    a = Agent(
        name="My Agent",
        slug="my-agent",
        provider_id=p.id,
        system_prompt="Be helpful.",
        role=AgentRole.ASSISTANT,
        config=AgentConfig(),
    )
    storage.save_agent(a)

    c = Conversation(agent_id=a.id, title="Test Chat")
    storage.save_conversation(c)

    return storage


def _patch_storage(monkeypatch, storage: InMemoryStorage) -> None:
    """Patch get_storage in all command modules to return the given storage."""
    # config.py does not import get_storage — omit it
    target_modules = [
        "ai_engine.adapters.cli.commands.provider",
        "ai_engine.adapters.cli.commands.agent",
        "ai_engine.adapters.cli.commands.conversation",
        "ai_engine.adapters.cli.commands.chat",
        "ai_engine.adapters.cli.utils",
    ]
    for mod in target_modules:
        monkeypatch.setattr(f"{mod}.get_storage", lambda db, _s=storage: _s)


# ── --version ─────────────────────────────────────────────────────────────────


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "ai-engine" in result.output


# ── provider list ─────────────────────────────────────────────────────────────


def test_provider_list_empty(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["provider", "list"])
    assert result.exit_code == 0
    assert "No providers" in result.output


def test_provider_list_populated(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["provider", "list"])
    assert result.exit_code == 0
    assert "OpenAI Test" in result.output


# ── provider show ─────────────────────────────────────────────────────────────


def test_provider_show_by_name(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["provider", "show", "OpenAI Test"])
    assert result.exit_code == 0
    assert "OpenAI Test" in result.output


def test_provider_show_not_found(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["provider", "show", "no-such-provider"])
    assert result.exit_code != 0


# ── provider add ──────────────────────────────────────────────────────────────


def test_provider_add(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(
        app,
        [
            "provider",
            "add",
            "--name",
            "Anthropic",
            "--type",
            "anthropic",
            "--model",
            "claude-3-5-sonnet-20241022",
        ],
    )
    assert result.exit_code == 0
    assert "Anthropic" in result.output
    providers = mem_storage.list_providers()
    assert any(p.name == "Anthropic" for p in providers)


def test_provider_add_invalid_type(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(
        app,
        [
            "provider",
            "add",
            "--name",
            "Bad",
            "--type",
            "not_a_real_provider",
            "--model",
            "model-x",
        ],
    )
    assert result.exit_code != 0


# ── provider delete ───────────────────────────────────────────────────────────


def test_provider_delete_with_yes(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["provider", "delete", "OpenAI Test", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


# ── agent list ────────────────────────────────────────────────────────────────


def test_agent_list_empty(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["agent", "list"])
    assert result.exit_code == 0
    assert "No agents" in result.output


def test_agent_list_populated(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["agent", "list"])
    assert result.exit_code == 0
    assert "My Agent" in result.output


# ── agent show ────────────────────────────────────────────────────────────────


def test_agent_show_by_slug(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["agent", "show", "my-agent"])
    assert result.exit_code == 0
    assert "My Agent" in result.output


def test_agent_show_not_found(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["agent", "show", "ghost"])
    assert result.exit_code != 0


# ── agent delete ──────────────────────────────────────────────────────────────


def test_agent_delete_with_yes(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["agent", "delete", "my-agent", "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


# ── conversation list ─────────────────────────────────────────────────────────


def test_conversation_list(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    result = runner.invoke(app, ["conversation", "list"])
    assert result.exit_code == 0
    assert "Test Chat" in result.output


def test_conversation_list_empty(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["conversation", "list"])
    assert result.exit_code == 0
    assert "No conversations" in result.output


# ── conversation show ─────────────────────────────────────────────────────────


def test_conversation_show(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    conv = populated_storage.list_conversations()[0]
    result = runner.invoke(app, ["conversation", "show", conv.id[:8]])
    assert result.exit_code == 0
    assert "Test Chat" in result.output


# ── conversation delete ───────────────────────────────────────────────────────


def test_conversation_delete_with_yes(monkeypatch, populated_storage):
    _patch_storage(monkeypatch, populated_storage)
    conv = populated_storage.list_conversations()[0]
    result = runner.invoke(app, ["conversation", "delete", conv.id[:8], "--yes"])
    assert result.exit_code == 0
    assert "deleted" in result.output.lower()


# ── config show ───────────────────────────────────────────────────────────────


def test_config_show(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "AI_ENGINE_DB" in result.output


def test_config_set_prints_export(monkeypatch, mem_storage):
    _patch_storage(monkeypatch, mem_storage)
    result = runner.invoke(app, ["config", "set", "AI_ENGINE_AGENT", "my-agent"])
    assert result.exit_code == 0
    assert "AI_ENGINE_AGENT" in result.output
