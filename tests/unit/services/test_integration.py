"""
Test d'intégration simple pour les services.
"""

import pytest
from unittest.mock import Mock, MagicMock

from ai_engine.models.provider import LLMProviderConfig
from ai_engine.services.agent import AgentService
from ai_engine.services.llm import LLMResponse
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.types import ProviderType


def test_agent_service_integration():
    """Test d'intégration basique du service agent."""
    # Setup
    storage = InMemoryStorage()
    agent_service = AgentService(storage)

    # Créer un provider
    provider = LLMProviderConfig(
        name="Test OpenAI",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4",
        api_key="sk-test-key",
    )
    saved_provider = storage.save_provider(provider)

    # Créer un agent
    agent = agent_service.create_agent(
        name="Test Agent",
        provider_id=saved_provider.id,
        system_prompt="You are a helpful assistant",
    )

    # Vérifications
    assert agent.id is not None
    assert agent.name == "Test Agent"
    assert agent.provider_id == saved_provider.id

    # Récupérer l'agent
    retrieved_agent = agent_service.get_agent(agent.id)
    assert retrieved_agent.id == agent.id

    # Créer une conversation
    conversation = agent_service.create_conversation(
        agent_id=agent.id, title="Test Conversation"
    )
    assert conversation.agent_id == agent.id


def test_llm_factory():
    """Test de la factory LLM."""
    from ai_engine.services.llm.factory import UnsupportedProviderError
    from ai_engine.services.llm import get_llm_client

    # Test provider non supporté
    provider = LLMProviderConfig(
        name="test-custom",
        provider_type=ProviderType.CUSTOM,
        default_model="custom-model",
    )

    with pytest.raises(UnsupportedProviderError):
        get_llm_client(provider)


if __name__ == "__main__":
    test_agent_service_integration()
    test_llm_factory()
    print("✅ Tests d'intégration services réussis!")
