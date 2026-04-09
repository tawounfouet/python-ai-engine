"""
Unit tests — FastAPI adapter.

Tous les tests utilisent un InMemoryStorage injecté via monkeypatch
sur `get_storage` dans chaque module router, ce qui évite tout I/O disque.

Le TestClient de Starlette/FastAPI est utilisé pour appeler les endpoints
comme de vraies requêtes HTTP, sans démarrer de serveur réel.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_engine.adapters.fastapi import create_router
from ai_engine.adapters.fastapi.exception_handlers import register_handlers
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.types import AgentRole, ProviderType


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def mem_storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def populated_storage() -> InMemoryStorage:
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

    c = Conversation(agent_id=a.id, title="Test Conv")
    storage.save_conversation(c)

    return storage


def _make_client(storage: Any, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """
    Crée un TestClient FastAPI avec le storage injecté via dependency_overrides.

    C'est le mécanisme officiel FastAPI pour remplacer des dépendances en tests :
    https://fastapi.tiangolo.com/advanced/testing-dependencies/
    """
    from ai_engine.adapters.fastapi.dependencies import get_storage as _real_get_storage

    fastapi_app = FastAPI()
    register_handlers(fastapi_app)
    fastapi_app.include_router(create_router(), prefix="/api")

    # Override la dépendance get_storage pour retourner notre storage en mémoire
    def _override_get_storage() -> Any:
        return storage

    fastapi_app.dependency_overrides[_real_get_storage] = _override_get_storage

    return TestClient(fastapi_app, raise_server_exceptions=True)


# ── Health / smoke ────────────────────────────────────────────────────────────


def test_router_mounts(monkeypatch, mem_storage):
    """Le router se monte sans erreur et les routes sont accessibles."""
    client = _make_client(mem_storage, monkeypatch)
    # openapi.json doit toujours répondre 200
    resp = client.get("/openapi.json")
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert any("/providers" in p for p in paths)
    assert any("/agents" in p for p in paths)
    assert any("/conversations" in p for p in paths)
    assert any("/chat" in p for p in paths)


# ── /providers ────────────────────────────────────────────────────────────────


def test_list_providers_empty(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_list_providers_populated(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    resp = client.get("/api/providers")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "OpenAI Test"


def test_create_provider(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post(
        "/api/providers",
        json={
            "name": "Anthropic",
            "provider_type": "anthropic",
            "default_model": "claude-3-5-sonnet-20241022",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Anthropic"
    assert data["has_api_key"] is False
    assert "id" in data
    # api_key must NOT be in response
    assert "api_key" not in data


def test_create_provider_with_key(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post(
        "/api/providers",
        json={
            "name": "OpenAI",
            "provider_type": "openai",
            "default_model": "gpt-4o",
            "api_key": "sk-secret",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["has_api_key"] is True
    assert "sk-secret" not in resp.text  # key must never leak


def test_create_provider_invalid_type(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post(
        "/api/providers",
        json={"name": "Bad", "provider_type": "invalid_xyz", "default_model": "m"},
    )
    assert resp.status_code == 422


def test_get_provider(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    provider_id = populated_storage.list_providers()[0].id
    resp = client.get(f"/api/providers/{provider_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == provider_id


def test_get_provider_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/providers/nonexistent-id")
    assert resp.status_code == 404


def test_update_provider(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    provider_id = populated_storage.list_providers()[0].id
    resp = client.patch(
        f"/api/providers/{provider_id}",
        json={"default_model": "gpt-4o", "is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["default_model"] == "gpt-4o"
    assert resp.json()["is_active"] is False


def test_delete_provider(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    provider_id = populated_storage.list_providers()[0].id
    resp = client.delete(f"/api/providers/{provider_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/providers/{provider_id}").status_code == 404


def test_delete_provider_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.delete("/api/providers/ghost")
    assert resp.status_code == 404


# ── /agents ───────────────────────────────────────────────────────────────────


def test_list_agents_empty(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_list_agents_populated(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    resp = client.get("/api/agents")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["name"] == "My Agent"


def test_create_agent(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    provider_id = populated_storage.list_providers()[0].id
    resp = client.post(
        "/api/agents",
        json={
            "name": "New Bot",
            "provider_id": provider_id,
            "system_prompt": "You are a bot.",
            "role": "assistant",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "New Bot"
    assert data["provider_id"] == provider_id


def test_create_agent_unknown_provider(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post(
        "/api/agents",
        json={"name": "Bot", "provider_id": "nonexistent-provider"},
    )
    assert resp.status_code == 404


def test_create_agent_invalid_role(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    provider_id = populated_storage.list_providers()[0].id
    resp = client.post(
        "/api/agents",
        json={"name": "Bot", "provider_id": provider_id, "role": "invalid_role"},
    )
    assert resp.status_code == 422


def test_get_agent_by_id(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id
    resp = client.get(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == agent_id


def test_get_agent_by_slug(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    resp = client.get("/api/agents/my-agent")
    assert resp.status_code == 200
    assert resp.json()["slug"] == "my-agent"


def test_get_agent_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/agents/ghost")
    assert resp.status_code == 404


def test_update_agent(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id
    resp = client.patch(
        f"/api/agents/{agent_id}",
        json={"name": "Updated Agent", "is_active": False},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Updated Agent"
    assert resp.json()["is_active"] is False


def test_delete_agent(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id
    resp = client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 204
    assert client.get(f"/api/agents/{agent_id}").status_code == 404


# ── /conversations ────────────────────────────────────────────────────────────


def test_list_conversations(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1
    assert resp.json()["items"][0]["title"] == "Test Conv"


def test_list_conversations_filter_by_agent(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id
    resp = client.get(f"/api/conversations?agent_id={agent_id}")
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_create_conversation(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id
    resp = client.post(
        "/api/conversations",
        json={"agent_id": agent_id, "title": "New Chat"},
    )
    assert resp.status_code == 201
    assert resp.json()["title"] == "New Chat"
    assert resp.json()["agent_id"] == agent_id


def test_create_conversation_unknown_agent(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post("/api/conversations", json={"agent_id": "ghost"})
    assert resp.status_code == 404


def test_get_conversation(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    conv_id = populated_storage.list_conversations()[0].id
    resp = client.get(f"/api/conversations/{conv_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == conv_id


def test_get_conversation_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/conversations/ghost")
    assert resp.status_code == 404


def test_delete_conversation(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    conv_id = populated_storage.list_conversations()[0].id
    resp = client.delete(f"/api/conversations/{conv_id}")
    assert resp.status_code == 204


def test_list_messages_empty(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    conv_id = populated_storage.list_conversations()[0].id
    resp = client.get(f"/api/conversations/{conv_id}/messages")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["items"] == []


def test_list_messages_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.get("/api/conversations/ghost/messages")
    assert resp.status_code == 404


# ── /chat ─────────────────────────────────────────────────────────────────────


def test_chat_agent_not_found(monkeypatch, mem_storage):
    client = _make_client(mem_storage, monkeypatch)
    resp = client.post(
        "/api/chat",
        json={"agent_id": "ghost", "message": "Hello"},
    )
    assert resp.status_code == 404


def test_chat_empty_message_rejected(monkeypatch, populated_storage):
    client = _make_client(populated_storage, monkeypatch)
    resp = client.post(
        "/api/chat",
        json={"agent_id": "my-agent", "message": ""},
    )
    # min_length=1 on message field → 422
    assert resp.status_code == 422


def test_chat_success(monkeypatch, populated_storage):
    """Chat endpoint calls svc.chat() and returns a ChatResponse."""
    from unittest.mock import MagicMock

    client = _make_client(populated_storage, monkeypatch)
    agent_id = populated_storage.list_agents()[0].id

    # Mock AgentService.chat to avoid real LLM call
    fake_msg = MagicMock()
    fake_msg.id = "msg-123"
    fake_msg.content = "Hello, I am your assistant."
    fake_msg.role = "assistant"

    fake_conv = MagicMock()
    fake_conv.id = "conv-456"

    monkeypatch.setattr(
        "ai_engine.services.agent.AgentService.chat",
        lambda self, *a, **kw: (fake_msg, fake_conv),
    )

    resp = client.post(
        "/api/chat",
        json={"agent_id": agent_id, "message": "Hello"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "Hello, I am your assistant."
    assert data["conversation_id"] == "conv-456"
    assert data["message_id"] == "msg-123"
    assert data["agent_id"] == agent_id


# ── Pagination ────────────────────────────────────────────────────────────────


def test_pagination_limit_offset(monkeypatch):
    storage = InMemoryStorage()
    # Add 5 providers
    for i in range(5):
        p = LLMProviderConfig(
            name=f"Provider {i}",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
        )
        storage.save_provider(p)

    client = _make_client(storage, monkeypatch)
    resp = client.get("/api/providers?limit=2&offset=0")
    assert resp.status_code == 200
    assert resp.json()["total"] == 5
    assert len(resp.json()["items"]) == 2

    resp2 = client.get("/api/providers?limit=2&offset=4")
    assert len(resp2.json()["items"]) == 1
