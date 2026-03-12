"""
Tests pour les services LLM et AgentService.

Tests d'intégration des services avec le storage layer.
"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, patch

from ai_engine.exceptions import ProviderNotFoundError, AgentNotFoundError
from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.services.agent import AgentService
from ai_engine.services.llm import LLMRequest, LLMResponse, get_llm_client
from ai_engine.storage.memory import InMemoryStorage
from ai_engine.types import AgentRole, MessageRole, ProviderType


class TestLLMClientFactory:
    """Tests pour la factory de clients LLM."""

    def test_unsupported_provider_type(self) -> None:
        """Test provider non supporté."""
        provider = LLMProviderConfig(
            name="test-custom",
            provider_type=ProviderType.CUSTOM,
            default_model="custom-model",
        )

        from ai_engine.services.llm.factory import UnsupportedProviderError

        with pytest.raises(
            UnsupportedProviderError,
            match="Custom providers must be registered separately",
        ):
            get_llm_client(provider)


class TestAgentService:
    """Tests pour AgentService."""

    @pytest.fixture
    def storage(self) -> InMemoryStorage:
        """Storage en mémoire pour les tests."""
        return InMemoryStorage()

    @pytest.fixture
    def agent_service(self, storage: InMemoryStorage) -> AgentService:
        """Service agent pour les tests."""
        return AgentService(storage)

    @pytest.fixture
    def sample_provider(self, storage: InMemoryStorage) -> LLMProviderConfig:
        """Provider de test."""
        provider = LLMProviderConfig(
            name="Test OpenAI",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
            api_key="sk-test-key",
        )
        return storage.save_provider(provider)

    def test_create_agent_success(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test création d'agent réussie."""
        agent = agent_service.create_agent(
            name="Test Agent",
            provider_id=sample_provider.id,
            system_prompt="You are a helpful assistant",
        )

        assert agent.id is not None
        assert agent.name == "Test Agent"
        assert agent.provider_id == sample_provider.id
        assert agent.system_prompt == "You are a helpful assistant"
        assert agent.role == AgentRole.ASSISTANT
        assert isinstance(agent.config, AgentConfig)

    def test_create_agent_provider_not_found(
        self,
        agent_service: AgentService,
    ) -> None:
        """Test création d'agent avec provider inexistant."""
        with pytest.raises(ProviderNotFoundError):
            agent_service.create_agent(
                name="Test Agent",
                provider_id="nonexistent-provider",
            )

    def test_get_agent_success(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test récupération d'agent réussie."""
        # Créer un agent
        created_agent = agent_service.create_agent(
            name="Test Agent",
            provider_id=sample_provider.id,
        )

        # Le récupérer
        retrieved_agent = agent_service.get_agent(created_agent.id)

        assert retrieved_agent.id == created_agent.id
        assert retrieved_agent.name == created_agent.name

    def test_get_agent_not_found(self, agent_service: AgentService) -> None:
        """Test récupération d'agent inexistant."""
        with pytest.raises(AgentNotFoundError):
            agent_service.get_agent("nonexistent-agent")

    def test_update_agent(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test mise à jour d'agent."""
        # Créer un agent
        agent = agent_service.create_agent(
            name="Original Name",
            provider_id=sample_provider.id,
        )

        # Le mettre à jour
        updated_agent = agent_service.update_agent(
            agent.id,
            name="Updated Name",
            system_prompt="New system prompt",
        )

        assert updated_agent.id == agent.id
        assert updated_agent.name == "Updated Name"
        assert updated_agent.system_prompt == "New system prompt"

    def test_delete_agent(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test suppression d'agent."""
        # Créer un agent
        agent = agent_service.create_agent(
            name="To Delete",
            provider_id=sample_provider.id,
        )

        # Le supprimer
        success = agent_service.delete_agent(agent.id)
        assert success is True

        # Vérifier qu'il n'existe plus
        with pytest.raises(AgentNotFoundError):
            agent_service.get_agent(agent.id)

    def test_list_agents(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test listage des agents."""
        # Créer plusieurs agents
        agent1 = agent_service.create_agent(
            name="Agent 1",
            provider_id=sample_provider.id,
            role=AgentRole.ASSISTANT,
        )
        agent2 = agent_service.create_agent(
            name="Agent 2",
            provider_id=sample_provider.id,
            role=AgentRole.RESEARCHER,
        )

        # Lister tous les agents
        all_agents = agent_service.list_agents()
        assert len(all_agents) == 2
        agent_ids = {agent.id for agent in all_agents}
        assert agent1.id in agent_ids
        assert agent2.id in agent_ids

        # Filtrer par rôle
        assistants = agent_service.list_agents(role=AgentRole.ASSISTANT)
        assert len(assistants) == 1
        assert assistants[0].id == agent1.id

    def test_create_conversation(
        self,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test création de conversation."""
        # Créer un agent
        agent = agent_service.create_agent(
            name="Chat Agent",
            provider_id=sample_provider.id,
        )

        # Créer une conversation
        conversation = agent_service.create_conversation(
            agent_id=agent.id,
            title="Test Chat",
        )

        assert conversation.id is not None
        assert conversation.agent_id == agent.id
        assert conversation.title == "Test Chat"

    @patch("ai_engine.services.llm.factory.get_llm_client")
    def test_chat_success(
        self,
        mock_get_llm_client: Mock,
        agent_service: AgentService,
        sample_provider: LLMProviderConfig,
    ) -> None:
        """Test conversation avec agent."""
        # Mock du client LLM
        mock_client = Mock()
        mock_response = LLMResponse(
            content="Hello! How can I help you?",
            model="gpt-4",
        )
        mock_client.complete.return_value = mock_response
        mock_get_llm_client.return_value = mock_client

        # Créer un agent
        agent = agent_service.create_agent(
            name="Chat Agent",
            provider_id=sample_provider.id,
            system_prompt="You are a helpful assistant",
        )

        # Envoyer un message
        response_message, conversation = agent_service.chat(
            agent_id=agent.id,
            message="Hello!",
        )

        # Vérifications
        assert response_message.content == "Hello! How can I help you?"
        assert response_message.role == MessageRole.ASSISTANT
        assert response_message.conversation_id == conversation.id
        assert conversation.agent_id == agent.id

        # Vérifier que le client a été appelé
        mock_get_llm_client.assert_called_once_with(sample_provider)
        mock_client.complete.assert_called_once()

        # Vérifier le contenu de la requête LLM
        call_args = mock_client.complete.call_args[0][0]
        assert isinstance(call_args, LLMRequest)

        # Doit contenir le system prompt et le message utilisateur
        messages = call_args.messages
        assert len(messages) >= 2
        assert messages[0].role == MessageRole.SYSTEM
        assert messages[0].content == "You are a helpful assistant"
        assert messages[-1].role == MessageRole.USER
        assert messages[-1].content == "Hello!"
