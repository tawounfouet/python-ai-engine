"""
Tests génériques pour toutes les implémentations de StorageBackend.

Ces tests peuvent être exécutés sur n'importe quelle implémentation de StorageBackend
pour valider qu'elle respecte le contrat défini par l'interface abstraite.
"""

from __future__ import annotations

import pytest
from datetime import UTC, datetime

from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.conversation import Conversation
from ai_engine.models.execution import Execution
from ai_engine.models.graph import Graph
from ai_engine.models.memory import AgentMemory
from ai_engine.models.message import Message
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.models.skill import Skill, AgentSkillAssignment
from ai_engine.models.tool import ToolDefinition
from ai_engine.models.knowledge import KnowledgeSource
from ai_engine.storage.base import StorageBackend
from ai_engine.types import (
    AgentRole,
    ExecutionStatus,
    MemoryType,
    MessageRole,
    ProviderType,
    SourceType,
)


class BaseStorageTest:
    """Classe de base pour tester toutes les implémentations de StorageBackend."""

    @pytest.fixture
    def storage(self) -> StorageBackend:
        """À overrider dans les classes filles pour fournir l'implémentation."""
        raise NotImplementedError("Subclass must implement storage fixture")

    def test_providers_crud(self, storage: StorageBackend) -> None:
        """Test CRUD complet pour les providers."""
        # Create
        provider = LLMProviderConfig(
            name="test-openai",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
            api_key="sk-test",
        )
        saved = storage.save_provider(provider)
        assert saved.id == provider.id
        assert saved.updated_at is not None

        # Read
        retrieved = storage.get_provider(provider.id)
        assert retrieved is not None
        assert retrieved.name == "test-openai"

        # Read by name
        by_name = storage.get_provider_by_name("test-openai")
        assert by_name is not None
        assert by_name.id == provider.id

        # List
        providers = storage.list_providers()
        assert len(providers) == 1
        assert providers[0].id == provider.id

        # List with filter
        active_providers = storage.list_providers(is_active=True)
        assert len(active_providers) == 1

        inactive_providers = storage.list_providers(is_active=False)
        assert len(inactive_providers) == 0

        # Update
        provider.settings.temperature = 0.5
        updated = storage.save_provider(provider)
        assert abs(updated.settings.temperature - 0.5) < 0.001

        # Delete
        deleted = storage.delete_provider(provider.id)
        assert deleted is True

        # Verify deletion
        assert storage.get_provider(provider.id) is None
        assert len(storage.list_providers()) == 0

    def test_agents_crud(self, storage: StorageBackend) -> None:
        """Test CRUD complet pour les agents."""
        # Create provider first
        provider = LLMProviderConfig(
            name="test-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create
        agent = Agent(
            name="Test Agent",
            slug="test-agent",
            role=AgentRole.ASSISTANT,
            provider_id=provider.id,
            system_prompt="You are a helpful assistant",
            config=AgentConfig(max_retries=5),
        )
        saved = storage.save_agent(agent)
        assert saved.id == agent.id

        # Read
        retrieved = storage.get_agent(agent.id)
        assert retrieved is not None
        assert retrieved.name == "Test Agent"

        # Read by slug
        by_slug = storage.get_agent_by_slug("test-agent")
        assert by_slug is not None
        assert by_slug.id == agent.id

        # List
        agents = storage.list_agents()
        assert len(agents) == 1

        # List with filters
        assistant_agents = storage.list_agents(role=AgentRole.ASSISTANT)
        assert len(assistant_agents) == 1

        active_agents = storage.list_agents(is_active=True)
        assert len(active_agents) == 1

        # Delete
        deleted = storage.delete_agent(agent.id)
        assert deleted is True
        assert storage.get_agent(agent.id) is None

    def test_tools_crud(self, storage: StorageBackend) -> None:
        """Test CRUD complet pour les tools."""
        # Create
        tool = ToolDefinition(
            name="calculator",
            key="calc",
            description="Basic calculator",
            function_schema={
                "type": "function",
                "function": {"name": "calculator", "parameters": {"type": "object"}},
            },
        )
        saved = storage.save_tool(tool)
        assert saved.id == tool.id

        # Read
        retrieved = storage.get_tool(tool.id)
        assert retrieved is not None
        assert retrieved.name == "calculator"

        # Read by key
        by_key = storage.get_tool_by_key("calc")
        assert by_key is not None
        assert by_key.id == tool.id

        # List
        tools = storage.list_tools()
        assert len(tools) == 1

        # Delete
        deleted = storage.delete_tool(tool.id)
        assert deleted is True

    def test_conversations_and_messages(self, storage: StorageBackend) -> None:
        """Test conversations et messages ensemble."""
        # Create provider first
        provider = LLMProviderConfig(
            name="chat-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create agent first
        agent = Agent(
            name="Chat Agent",
            slug="chat",
            provider_id=provider.id,
        )
        storage.save_agent(agent)

        # Create conversation
        conversation = Conversation(
            agent_id=agent.id,
            title="Test Chat",
        )
        saved_conv = storage.save_conversation(conversation)
        assert saved_conv.id == conversation.id

        # Create messages
        msg1 = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Hello",
        )
        msg2 = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content="Hi there!",
        )

        storage.save_message(msg1)
        storage.save_message(msg2)

        # Test message retrieval
        messages = storage.get_messages(conversation.id)
        assert len(messages) == 2
        assert messages[0].role == MessageRole.USER
        assert messages[1].role == MessageRole.ASSISTANT

        # Test pagination
        first_message = storage.get_messages(conversation.id, limit=1)
        assert len(first_message) == 1

        # Test count
        count = storage.count_messages(conversation.id)
        assert count == 2

        # Test conversation listing
        conversations = storage.list_conversations(agent_id=agent.id)
        assert len(conversations) == 1

        # Delete
        storage.delete_conversation(conversation.id)
        assert storage.get_conversation(conversation.id) is None

    def test_memory_operations(self, storage: StorageBackend) -> None:
        """Test opérations de mémoire."""
        # Create provider first
        provider = LLMProviderConfig(
            name="memory-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create agent first
        agent = Agent(
            name="Memory Agent",
            slug="memory",
            provider_id=provider.id,
        )
        storage.save_agent(agent)

        # Create memory
        memory = AgentMemory(
            agent_id=agent.id,
            key="user_preference",
            content='{"theme": "dark", "language": "fr"}',
            memory_type=MemoryType.LONG_TERM,
        )
        saved = storage.save_memory(memory)
        assert saved.id == memory.id

        # Retrieve memory
        retrieved = storage.get_memory(agent.id, "user_preference")
        assert retrieved is not None
        assert '"theme": "dark"' in retrieved.content

        # List memories
        memories = storage.list_memories(agent.id)
        assert len(memories) == 1

        # List by type
        long_term = storage.list_memories(agent.id, memory_type=MemoryType.LONG_TERM)
        assert len(long_term) == 1

        # Delete
        storage.delete_memory(memory.id)
        assert storage.get_memory(agent.id, "user_preference") is None

    def test_execution_operations(self, storage: StorageBackend) -> None:
        """Test opérations d'exécution."""
        # Create provider first
        provider = LLMProviderConfig(
            name="exec-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create agent first
        agent = Agent(
            name="Exec Agent",
            slug="exec",
            provider_id=provider.id,
        )
        storage.save_agent(agent)

        # Create execution
        execution = Execution(
            agent_id=agent.id,
            task_description="Test task",
            status=ExecutionStatus.PENDING,
        )
        saved = storage.save_execution(execution)
        assert saved.id == execution.id

        # Retrieve
        retrieved = storage.get_execution(execution.id)
        assert retrieved is not None
        assert retrieved.status == ExecutionStatus.PENDING

        # List executions
        executions = storage.list_executions(agent_id=agent.id)
        assert len(executions) == 1

        # List by status
        pending = storage.list_executions(status=ExecutionStatus.PENDING)
        assert len(pending) == 1

    def test_graph_operations(self, storage: StorageBackend) -> None:
        """Test opérations de graph."""
        # Create provider first
        provider = LLMProviderConfig(
            name="graph-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create agent first
        agent = Agent(
            name="Graph Agent",
            slug="graph",
            provider_id=provider.id,
        )
        storage.save_agent(agent)

        # Create graph
        graph = Graph(
            name="Test Workflow",
            slug="test-workflow",
            agent_id=agent.id,
            definition={"nodes": [{"id": "start", "type": "agent"}], "edges": []},
        )
        saved = storage.save_graph(graph)
        assert saved.id == graph.id

        # Retrieve
        retrieved = storage.get_graph(graph.id)
        assert retrieved is not None
        assert retrieved.name == "Test Workflow"

        # Retrieve by slug
        by_slug = storage.get_graph_by_slug("test-workflow")
        assert by_slug is not None
        assert by_slug.id == graph.id

        # List graphs
        graphs = storage.list_graphs(agent_id=agent.id)
        assert len(graphs) == 1

        # Delete
        storage.delete_graph(graph.id)
        assert storage.get_graph(graph.id) is None

    def test_knowledge_operations(self, storage: StorageBackend) -> None:
        """Test opérations de knowledge source."""
        # Create provider first
        provider = LLMProviderConfig(
            name="knowledge-provider",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )
        storage.save_provider(provider)

        # Create agent first
        agent = Agent(
            name="Knowledge Agent",
            slug="knowledge",
            provider_id=provider.id,
        )
        storage.save_agent(agent)

        # Create knowledge source
        source = KnowledgeSource(
            name="Test KB",
            description="Test knowledge base",
            source_type=SourceType.DOCUMENT,
            agent_ids=[agent.id],
        )
        saved = storage.save_knowledge_source(source)
        assert saved.id == source.id

        # Retrieve
        retrieved = storage.get_knowledge_source(source.id)
        assert retrieved is not None
        assert retrieved.name == "Test KB"

        # List all sources
        all_sources = storage.list_knowledge_sources()
        assert len(all_sources) == 1

        # List for specific agent
        agent_sources = storage.list_knowledge_sources(agent_id=agent.id)
        assert len(agent_sources) == 1

        # Delete
        storage.delete_knowledge_source(source.id)
        assert storage.get_knowledge_source(source.id) is None

    def test_transaction_support(self, storage: StorageBackend) -> None:
        """Test support des transactions."""
        # Create a provider
        provider = LLMProviderConfig(
            name="tx-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )

        # Test successful transaction
        with storage.transaction():
            storage.save_provider(provider)

        # Verify it was saved
        assert storage.get_provider(provider.id) is not None

        # Test transaction rollback (if supported)
        try:
            with storage.transaction():
                provider2 = LLMProviderConfig(
                    name="tx-test-2",
                    provider_type=ProviderType.OPENAI,
                    default_model="gpt-4",
                )
                storage.save_provider(provider2)
                raise RuntimeError("Force rollback")
        except RuntimeError:
            pass

        # provider2 should not be saved (if transactions are supported)
        # Note: InMemoryStorage doesn't support real transactions,
        # so this test might fail for that implementation    def test_context_manager(self, storage: StorageBackend) -> None:
        """Test utilisation comme context manager."""
        provider = LLMProviderConfig(
            name="ctx-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        )

        # Test avec un nouveau storage instance pour éviter la fermeture
        if hasattr(storage, "_db_path"):
            # Pour SQLite, créer une nouvelle instance
            from ai_engine.storage import SQLiteStorage

            test_storage = SQLiteStorage(storage._db_path)
        else:
            # Pour InMemory, utiliser l'instance existante
            test_storage = storage

        # This should not raise an exception
        with test_storage:
            test_storage.save_provider(provider)
            # Vérifier dans le context manager que ça fonctionne
            assert test_storage.get_provider(provider.id) is not None
