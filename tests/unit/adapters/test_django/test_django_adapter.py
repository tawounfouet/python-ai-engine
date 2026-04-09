"""
Tests — AI Engine Django Adapter (Phase 5.3).

Tests couverts :
  - DjangoORMStorage : CRUD providers, agents, conversations, messages
  - Serializers DRF  : validation + rendu
  - Views DRF        : via APIClient (sans LLM réel)
  - AppConfig        : ready() sans crash
  - urls             : urlpatterns montables
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(db):  # db = pytest-django fixture that creates tables
    from ai_engine.adapters.django import DjangoORMStorage

    return DjangoORMStorage()


def _make_provider(**kwargs):
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.types import ProviderType

    defaults = dict(
        name="Test Provider",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
    )
    defaults.update(kwargs)
    return LLMProviderConfig(**defaults)


def _make_agent(provider_id: str, **kwargs):
    from ai_engine.models.agent import Agent

    defaults = dict(
        name="Test Agent",
        slug="test-agent",
        provider_id=provider_id,
        system_prompt="You are a test agent.",
    )
    defaults.update(kwargs)
    return Agent(**defaults)


def _make_conversation(agent_id: str, **kwargs):
    from ai_engine.models.conversation import Conversation

    defaults = dict(agent_id=agent_id, title="Test Conv")
    defaults.update(kwargs)
    return Conversation(**defaults)


def _make_message(conversation_id: str, **kwargs):
    from ai_engine.models.message import Message
    from ai_engine.types import MessageRole

    defaults = dict(
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Hello!",
    )
    defaults.update(kwargs)
    return Message(**defaults)


# ---------------------------------------------------------------------------
# DjangoORMStorage — Providers
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_and_get_provider(storage):
    provider = _make_provider()
    saved = storage.save_provider(provider)
    assert saved.id == provider.id

    fetched = storage.get_provider(provider.id)
    assert fetched is not None
    assert fetched.name == "Test Provider"
    assert fetched.provider_type.value == "openai"


@pytest.mark.django_db
def test_get_provider_not_found(storage):
    assert storage.get_provider("nonexistent-id") is None


@pytest.mark.django_db
def test_get_provider_by_name(storage):
    provider = _make_provider(name="Unique Provider")
    storage.save_provider(provider)
    found = storage.get_provider_by_name("Unique Provider")
    assert found is not None
    assert found.id == provider.id


@pytest.mark.django_db
def test_list_providers_empty(storage):
    assert storage.list_providers() == []


@pytest.mark.django_db
def test_list_providers(storage):
    storage.save_provider(_make_provider(name="P1"))
    storage.save_provider(_make_provider(name="P2"))
    providers = storage.list_providers()
    assert len(providers) == 2
    names = {p.name for p in providers}
    assert names == {"P1", "P2"}


@pytest.mark.django_db
def test_list_providers_filter_active(storage):
    storage.save_provider(_make_provider(name="Active", is_active=True))
    storage.save_provider(_make_provider(name="Inactive", is_active=False))
    assert len(storage.list_providers(is_active=True)) == 1
    assert len(storage.list_providers(is_active=False)) == 1
    assert len(storage.list_providers()) == 2


@pytest.mark.django_db
def test_delete_provider(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    assert storage.delete_provider(provider.id) is True
    assert storage.get_provider(provider.id) is None


@pytest.mark.django_db
def test_delete_provider_not_found(storage):
    assert storage.delete_provider("nonexistent") is False


# ---------------------------------------------------------------------------
# DjangoORMStorage — Agents
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_and_get_agent(storage):
    provider = _make_provider()
    storage.save_provider(provider)

    agent = _make_agent(provider.id)
    saved = storage.save_agent(agent)
    assert saved.id == agent.id

    fetched = storage.get_agent(agent.id)
    assert fetched is not None
    assert fetched.name == "Test Agent"
    assert fetched.slug == "test-agent"


@pytest.mark.django_db
def test_get_agent_by_slug(storage):
    provider = _make_provider()
    storage.save_provider(provider)

    agent = _make_agent(provider.id, slug="my-bot")
    storage.save_agent(agent)

    found = storage.get_agent_by_slug("my-bot")
    assert found is not None
    assert found.id == agent.id


@pytest.mark.django_db
def test_get_agent_not_found(storage):
    assert storage.get_agent("bad-id") is None
    assert storage.get_agent_by_slug("bad-slug") is None


@pytest.mark.django_db
def test_list_agents(storage):
    provider = _make_provider()
    storage.save_provider(provider)

    storage.save_agent(_make_agent(provider.id, slug="bot-1", name="Bot 1"))
    storage.save_agent(_make_agent(provider.id, slug="bot-2", name="Bot 2"))
    assert len(storage.list_agents()) == 2


@pytest.mark.django_db
def test_list_agents_filter_active(storage):
    provider = _make_provider()
    storage.save_provider(provider)

    storage.save_agent(_make_agent(provider.id, slug="active-bot", is_active=True))
    storage.save_agent(_make_agent(provider.id, slug="inactive-bot", is_active=False))
    assert len(storage.list_agents(is_active=True)) == 1
    assert len(storage.list_agents(is_active=False)) == 1


@pytest.mark.django_db
def test_delete_agent(storage):
    provider = _make_provider()
    storage.save_provider(provider)

    agent = _make_agent(provider.id)
    storage.save_agent(agent)
    assert storage.delete_agent(agent.id) is True
    assert storage.get_agent(agent.id) is None


# ---------------------------------------------------------------------------
# DjangoORMStorage — Conversations
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_and_get_conversation(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent = _make_agent(provider.id)
    storage.save_agent(agent)

    conv = _make_conversation(agent.id)
    saved = storage.save_conversation(conv)
    assert saved.id == conv.id

    fetched = storage.get_conversation(conv.id)
    assert fetched is not None
    assert fetched.agent_id == agent.id


@pytest.mark.django_db
def test_get_conversation_not_found(storage):
    assert storage.get_conversation("bad-id") is None


@pytest.mark.django_db
def test_list_conversations_filter_by_agent(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent1 = _make_agent(provider.id, slug="bot-a")
    agent2 = _make_agent(provider.id, slug="bot-b")
    storage.save_agent(agent1)
    storage.save_agent(agent2)

    storage.save_conversation(_make_conversation(agent1.id))
    storage.save_conversation(_make_conversation(agent1.id))
    storage.save_conversation(_make_conversation(agent2.id))

    assert len(storage.list_conversations(agent_id=agent1.id)) == 2
    assert len(storage.list_conversations(agent_id=agent2.id)) == 1
    assert len(storage.list_conversations()) == 3


@pytest.mark.django_db
def test_delete_conversation(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent = _make_agent(provider.id)
    storage.save_agent(agent)

    conv = _make_conversation(agent.id)
    storage.save_conversation(conv)
    assert storage.delete_conversation(conv.id) is True
    assert storage.get_conversation(conv.id) is None


# ---------------------------------------------------------------------------
# DjangoORMStorage — Messages
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_save_and_get_messages(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent = _make_agent(provider.id)
    storage.save_agent(agent)
    conv = _make_conversation(agent.id)
    storage.save_conversation(conv)

    from ai_engine.types import MessageRole

    storage.save_message(
        _make_message(conv.id, content="Hello!", role=MessageRole.USER)
    )
    storage.save_message(
        _make_message(conv.id, content="Hi there!", role=MessageRole.ASSISTANT)
    )

    messages = storage.get_messages(conv.id)
    assert len(messages) == 2


@pytest.mark.django_db
def test_count_messages(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent = _make_agent(provider.id)
    storage.save_agent(agent)
    conv = _make_conversation(agent.id)
    storage.save_conversation(conv)

    assert storage.count_messages(conv.id) == 0
    storage.save_message(_make_message(conv.id))
    storage.save_message(_make_message(conv.id))
    assert storage.count_messages(conv.id) == 2


@pytest.mark.django_db
def test_get_messages_with_limit_offset(storage):
    provider = _make_provider()
    storage.save_provider(provider)
    agent = _make_agent(provider.id)
    storage.save_agent(agent)
    conv = _make_conversation(agent.id)
    storage.save_conversation(conv)

    for i in range(5):
        storage.save_message(_make_message(conv.id, content=f"msg {i}"))

    first2 = storage.get_messages(conv.id, limit=2, offset=0)
    assert len(first2) == 2

    last3 = storage.get_messages(conv.id, limit=3, offset=2)
    assert len(last3) == 3


# ---------------------------------------------------------------------------
# DRF Serializers
# ---------------------------------------------------------------------------


def test_provider_serializer_hides_api_key():
    from ai_engine.adapters.django.serializers import ProviderSerializer
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.types import ProviderType

    provider = LLMProviderConfig(
        name="OpenAI",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o",
        api_key="sk-secret",
    )
    data = ProviderSerializer(provider).data
    assert "api_key" not in data
    assert data["has_api_key"] is True
    assert data["name"] == "OpenAI"


def test_provider_serializer_no_api_key():
    from ai_engine.adapters.django.serializers import ProviderSerializer
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.types import ProviderType

    provider = LLMProviderConfig(
        name="Ollama",
        provider_type=ProviderType.OLLAMA,
        default_model="llama3",
    )
    data = ProviderSerializer(provider).data
    assert data["has_api_key"] is False


def test_provider_create_serializer_valid():
    from ai_engine.adapters.django.serializers import ProviderCreateSerializer

    s = ProviderCreateSerializer(
        data={"name": "Test", "provider_type": "openai", "default_model": "gpt-4o"}
    )
    assert s.is_valid(), s.errors


def test_provider_create_serializer_missing_required():
    from ai_engine.adapters.django.serializers import ProviderCreateSerializer

    s = ProviderCreateSerializer(data={"name": "Test"})
    assert not s.is_valid()
    assert "provider_type" in s.errors or "default_model" in s.errors


def test_agent_create_serializer_valid():
    from ai_engine.adapters.django.serializers import AgentCreateSerializer

    s = AgentCreateSerializer(
        data={
            "name": "Bot",
            "provider_id": "some-id",
            "system_prompt": "You are a bot.",
        }
    )
    assert s.is_valid(), s.errors


def test_chat_request_serializer_rejects_empty_message():
    from ai_engine.adapters.django.serializers import ChatRequestSerializer

    s = ChatRequestSerializer(data={"agent_id": "x", "message": ""})
    assert not s.is_valid()
    assert "message" in s.errors


# ---------------------------------------------------------------------------
# DRF Views — via Django test client
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_views_list_providers_empty():
    from django.test import RequestFactory

    from ai_engine.adapters.django.views import ProviderListCreateView

    factory = RequestFactory()
    request = factory.get("/providers/")
    response = ProviderListCreateView.as_view()(request)
    assert response.status_code == 200
    assert response.data["total"] == 0
    assert response.data["items"] == []


@pytest.mark.django_db
def test_views_create_provider():
    from django.test import RequestFactory
    import json

    from ai_engine.adapters.django.views import ProviderListCreateView

    factory = RequestFactory()
    body = json.dumps(
        {
            "name": "OpenAI",
            "provider_type": "openai",
            "default_model": "gpt-4o",
        }
    ).encode()
    request = factory.post("/providers/", data=body, content_type="application/json")
    response = ProviderListCreateView.as_view()(request)
    assert response.status_code == 201, getattr(response, "data", response)
    assert response.data["name"] == "OpenAI"
    assert "api_key" not in response.data
    assert response.data["has_api_key"] is False


@pytest.mark.django_db
def test_views_create_provider_invalid_type():
    from django.test import RequestFactory
    import json

    from ai_engine.adapters.django.views import ProviderListCreateView

    factory = RequestFactory()
    body = json.dumps(
        {
            "name": "Bad",
            "provider_type": "does_not_exist",
            "default_model": "x",
        }
    ).encode()
    request = factory.post("/providers/", data=body, content_type="application/json")
    response = ProviderListCreateView.as_view()(request)
    assert response.status_code == 422


@pytest.mark.django_db
def test_views_get_provider_not_found():
    from django.test import RequestFactory

    from ai_engine.adapters.django.views import ProviderDetailView

    factory = RequestFactory()
    request = factory.get("/providers/bad-id/")
    # DRF's APIView catches NotFound and returns a 404 Response — it never propagates
    response = ProviderDetailView.as_view()(request, provider_id="bad-id")
    assert response.status_code == 404


@pytest.mark.django_db
def test_views_list_agents_empty():
    from django.test import RequestFactory

    from ai_engine.adapters.django.views import AgentListCreateView

    factory = RequestFactory()
    response = AgentListCreateView.as_view()(factory.get("/agents/"))
    assert response.status_code == 200
    assert response.data["total"] == 0


@pytest.mark.django_db
def test_views_create_agent_unknown_provider():
    from django.test import RequestFactory
    import json

    from ai_engine.adapters.django.views import AgentListCreateView

    factory = RequestFactory()
    body = json.dumps(
        {
            "name": "Bot",
            "provider_id": "nonexistent-provider",
            "system_prompt": "You are a bot.",
        }
    ).encode()
    request = factory.post("/agents/", data=body, content_type="application/json")
    response = AgentListCreateView.as_view()(request)
    assert response.status_code == 404


@pytest.mark.django_db
def test_views_full_provider_and_agent_flow():
    from django.test import RequestFactory
    import json

    from ai_engine.adapters.django.views import (
        AgentDetailView,
        AgentListCreateView,
        ProviderListCreateView,
    )

    factory = RequestFactory()

    # Create provider
    body = json.dumps(
        {
            "name": "OpenAI",
            "provider_type": "openai",
            "default_model": "gpt-4o",
        }
    ).encode()
    resp = ProviderListCreateView.as_view()(
        factory.post("/providers/", data=body, content_type="application/json")
    )
    assert resp.status_code == 201
    provider_id = resp.data["id"]

    # Create agent
    body = json.dumps(
        {
            "name": "Code Bot",
            "provider_id": provider_id,
            "system_prompt": "You are a code reviewer.",
            "role": "assistant",
        }
    ).encode()
    resp = AgentListCreateView.as_view()(
        factory.post("/agents/", data=body, content_type="application/json")
    )
    assert resp.status_code == 201
    agent_id = resp.data["id"]
    assert resp.data["slug"] == "code-bot"

    # Get agent by id
    resp = AgentDetailView.as_view()(
        factory.get(f"/agents/{agent_id}/"),
        agent_id=agent_id,
    )
    assert resp.status_code == 200
    assert resp.data["name"] == "Code Bot"

    # Delete agent
    resp = AgentDetailView.as_view()(
        factory.delete(f"/agents/{agent_id}/"),
        agent_id=agent_id,
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# App config
# ---------------------------------------------------------------------------


def test_app_config_label():
    from ai_engine.adapters.django.apps import AiEngineConfig

    assert AiEngineConfig.label == "ai_engine"
    assert AiEngineConfig.verbose_name == "AI Engine"


# ---------------------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------------------


def test_urlpatterns_exist():
    from ai_engine.adapters.django.urls import urlpatterns

    names = {p.name for p in urlpatterns}
    assert "ai_engine-provider-list" in names
    assert "ai_engine-agent-list" in names
    assert "ai_engine-conversation-list" in names
    assert "ai_engine-chat" in names
    assert "ai_engine-conversation-messages" in names
    assert len(urlpatterns) == 8
