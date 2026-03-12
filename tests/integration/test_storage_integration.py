"""
Tests d'intégration pour la couche Storage.

Tests qui vérifient l'interopérabilité et la cohérence entre différentes
implémentations de StorageBackend.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ai_engine.models.agent import Agent, AgentConfig
from ai_engine.models.provider import LLMProviderConfig, ProviderType
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message, MessageRole
from ai_engine.storage import InMemoryStorage, SQLiteStorage
from ai_engine.types import AgentRole


class TestStorageInteroperability:
    """Tests d'interopérabilité entre différentes implémentations."""

    def test_data_migration_memory_to_sqlite(self) -> None:
        """Test migration de données de InMemory vers SQLite."""
        # Préparer des données dans InMemoryStorage
        memory_storage = InMemoryStorage()

        # Créer des entités de test
        provider = LLMProviderConfig(
            name="migration-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
            config={"model": "gpt-4"},
        )

        agent = Agent(
            name="Migration Agent",
            slug="migrate",
            role=AgentRole.ASSISTANT,
            provider_id=provider.id,
            config=AgentConfig(max_retries=5),
        )

        conversation = Conversation(
            agent_id=agent.id,
            title="Test Migration",
        )

        message = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content="Hello migration test!",
        )

        # Sauvegarder dans memory storage
        memory_storage.save_provider(provider)
        memory_storage.save_agent(agent)
        memory_storage.save_conversation(conversation)
        memory_storage.save_message(message)

        # Créer SQLite storage
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            sqlite_storage = SQLiteStorage(db_path)

            # Migrer les données
            self._migrate_storage_data(memory_storage, sqlite_storage)

            # Vérifier que toutes les données sont présentes
            assert sqlite_storage.get_provider(provider.id) is not None
            assert sqlite_storage.get_agent(agent.id) is not None
            assert sqlite_storage.get_conversation(conversation.id) is not None

            messages = sqlite_storage.get_messages(conversation.id)
            assert len(messages) == 1
            assert messages[0].content == "Hello migration test!"

            # Vérifier l'intégrité des relations
            migrated_agent = sqlite_storage.get_agent(agent.id)
            assert migrated_agent.provider_id == provider.id

            migrated_conversation = sqlite_storage.get_conversation(conversation.id)
            assert migrated_conversation.agent_id == agent.id

            sqlite_storage.close()

        finally:
            Path(db_path).unlink(missing_ok=True)

    def _migrate_storage_data(
        self, source: InMemoryStorage, target: SQLiteStorage
    ) -> None:
        """Helper pour migrer toutes les données d'un storage vers un autre."""
        # Migrer providers
        for provider in source.list_providers():
            target.save_provider(provider)

        # Migrer agents
        for agent in source.list_agents():
            target.save_agent(agent)

        # Migrer tools
        for tool in source.list_tools():
            target.save_tool(tool)

        # Migrer skills
        for skill in source.list_skills():
            target.save_skill(skill)

        # Migrer conversations
        for conversation in source.list_conversations():
            target.save_conversation(conversation)

            # Migrer les messages de cette conversation
            messages = source.get_messages(conversation.id)
            for message in messages:
                target.save_message(message)

        # Migrer executions
        for execution in source.list_executions():
            target.save_execution(execution)

            # Migrer les steps de cette execution
            steps = source.get_execution_steps(execution.id)
            for step in steps:
                target.save_execution_step(step)

        # Migrer graphs
        for graph in source.list_graphs():
            target.save_graph(graph)

        # Migrer knowledge sources
        for knowledge_source in source.list_knowledge_sources():
            target.save_knowledge_source(knowledge_source)

    def test_storage_consistency_across_implementations(self) -> None:
        """Test que les mêmes données produisent les mêmes résultats."""
        # Données de test
        provider = LLMProviderConfig(
            name="consistency-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
            metadata={"model": "gpt-4", "temperature": 0.7},
        )

        # Test sur InMemoryStorage
        memory_storage = InMemoryStorage()
        memory_storage.save_provider(provider)

        memory_providers = memory_storage.list_providers()
        memory_provider = memory_storage.get_provider(provider.id)
        memory_by_name = memory_storage.get_provider_by_name("consistency-test")

        # Test sur SQLiteStorage
        sqlite_storage = SQLiteStorage(":memory:")
        sqlite_storage.save_provider(provider)

        sqlite_providers = sqlite_storage.list_providers()
        sqlite_provider = sqlite_storage.get_provider(provider.id)
        sqlite_by_name = sqlite_storage.get_provider_by_name("consistency-test")

        # Vérifier la consistance
        assert len(memory_providers) == len(sqlite_providers) == 1

        assert memory_provider.id == sqlite_provider.id == provider.id
        assert memory_provider.name == sqlite_provider.name == provider.name
        assert memory_provider.metadata == sqlite_provider.metadata == provider.metadata

        assert memory_by_name.id == sqlite_by_name.id == provider.id

        memory_storage.close()
        sqlite_storage.close()

    def test_concurrent_storage_operations(self) -> None:
        """Test basique d'opérations simultanées sur différents storages."""
        memory_storage = InMemoryStorage()
        sqlite_storage = SQLiteStorage(":memory:")

        # Créer des agents avec des IDs différents
        agent1 = Agent(name="Agent Memory", slug="agent-memory", provider_id="test-provider")
        agent2 = Agent(name="Agent SQLite", slug="agent-sqlite", provider_id="test-provider")

        # Opérations simultanées
        memory_storage.save_agent(agent1)
        sqlite_storage.save_agent(agent2)

        # Vérifier l'isolation
        assert memory_storage.get_agent(agent1.id) is not None
        assert memory_storage.get_agent(agent2.id) is None

        assert sqlite_storage.get_agent(agent2.id) is not None
        assert sqlite_storage.get_agent(agent1.id) is None

        # Listes séparées
        memory_agents = memory_storage.list_agents()
        sqlite_agents = sqlite_storage.list_agents()

        assert len(memory_agents) == 1
        assert len(sqlite_agents) == 1
        assert memory_agents[0].id != sqlite_agents[0].id

        memory_storage.close()
        sqlite_storage.close()


class TestStorageEdgeCases:
    """Tests de cas limites et d'erreurs."""

    def test_nonexistent_entity_operations(self) -> None:
        """Test opérations sur des entités inexistantes."""
        storage = InMemoryStorage()

        # Get inexistants
        assert storage.get_provider("nonexistent") is None
        assert storage.get_agent("nonexistent") is None
        assert storage.get_tool("nonexistent") is None
        assert storage.get_conversation("nonexistent") is None

        # Delete inexistants
        assert storage.delete_provider("nonexistent") is False
        assert storage.delete_agent("nonexistent") is False
        assert storage.delete_tool("nonexistent") is False

        # Listes vides
        assert len(storage.list_providers()) == 0
        assert len(storage.list_agents()) == 0
        assert len(storage.get_messages("nonexistent")) == 0
        assert storage.count_messages("nonexistent") == 0

    def test_empty_filters(self) -> None:
        """Test filtres avec résultats vides."""
        storage = InMemoryStorage()

        # Créer quelques entités
        provider = LLMProviderConfig(
            name="filter-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            is_active=True,
        )
        storage.save_provider(provider)

        agent = Agent(
            name="Filter Agent",
            slug="filter",
            role=AgentRole.ASSISTANT,
            provider_id=provider.id,
            is_active=True,
        )
        storage.save_agent(agent)

        # Filtres qui ne matchent rien
        inactive_providers = storage.list_providers(is_active=False)
        assert len(inactive_providers) == 0

        inactive_agents = storage.list_agents(is_active=False)
        assert len(inactive_agents) == 0

        researcher_agents = storage.list_agents(role=AgentRole.RESEARCHER)
        assert len(researcher_agents) == 0

    def test_large_data_handling(self) -> None:
        """Test basique avec de plus grandes quantités de données."""
        storage = SQLiteStorage(":memory:")

        # Créer un agent
        agent = Agent(name="Bulk Agent", slug="bulk", provider_id="test-provider")
        storage.save_agent(agent)

        # Créer une conversation
        conversation = Conversation(agent_id=agent.id, title="Bulk Test")
        storage.save_conversation(conversation)

        # Créer beaucoup de messages
        num_messages = 1000
        for i in range(num_messages):
            message = Message(
                conversation_id=conversation.id,
                role=MessageRole.USER if i % 2 == 0 else MessageRole.ASSISTANT,
                content=f"Message #{i}",
            )
            storage.save_message(message)

        # Vérifier le count
        assert storage.count_messages(conversation.id) == num_messages

        # Test pagination
        first_100 = storage.get_messages(conversation.id, limit=100)
        assert len(first_100) == 100

        next_100 = storage.get_messages(conversation.id, limit=100, offset=100)
        assert len(next_100) == 100

        # Vérifier que les messages sont différents
        first_ids = {msg.id for msg in first_100}
        next_ids = {msg.id for msg in next_100}
        assert first_ids.isdisjoint(next_ids)

        storage.close()

    def test_unicode_and_special_characters(self) -> None:
        """Test gestion des caractères spéciaux et Unicode."""
        storage = SQLiteStorage(":memory:")

        # Données avec caractères spéciaux
        provider = LLMProviderConfig(
            name="测试-Provider-🤖",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            metadata={"description": "Émojis: 🚀🎯 Unicode: café naïve résumé"},
        )
        storage.save_provider(provider)

        agent = Agent(
            name="Agent François 🇫🇷",
            slug="agent-français",
            provider_id=provider.id,
            system_prompt="Bonjour! Je suis un assistant qui parle français. J'utilise des accents: é, è, à, ç",
        )
        storage.save_agent(agent)

        # Vérifier que tout est correctement sauvé et récupéré
        retrieved_provider = storage.get_provider(provider.id)
        assert retrieved_provider.name == "测试-Provider-🤖"
        assert "🚀🎯" in retrieved_provider.metadata["description"]

        retrieved_agent = storage.get_agent(agent.id)
        assert retrieved_agent.name == "Agent François 🇫🇷"
        assert "français" in retrieved_agent.system_prompt

        # Test recherche par nom avec caractères spéciaux
        by_name = storage.get_provider_by_name("测试-Provider-🤖")
        assert by_name is not None
        assert by_name.id == provider.id

        storage.close()
