"""
Tests spécifiques pour InMemoryStorage.

Hérite des tests génériques et ajoute des tests spécifiques à cette implémentation.
"""

from __future__ import annotations

import pytest

from ai_engine.storage import InMemoryStorage
from ai_engine.storage.base import StorageBackend
from tests.unit.storage.test_base_storage import BaseStorageTest


class TestInMemoryStorage(BaseStorageTest):
    """Tests pour InMemoryStorage."""

    @pytest.fixture
    def storage(self) -> StorageBackend:
        """Fournit une instance fraîche d'InMemoryStorage pour chaque test."""
        return InMemoryStorage()

    def test_multiple_instances_are_isolated(self) -> None:
        """Test que plusieurs instances sont isolées."""
        storage1 = InMemoryStorage()
        storage2 = InMemoryStorage()

        # Ajouter un provider dans storage1
        from ai_engine.models.provider import LLMProviderConfig, ProviderType

        provider = LLMProviderConfig(
            name="test-isolation",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
        )
        storage1.save_provider(provider)

        # Vérifier que storage2 ne le voit pas
        assert storage1.get_provider(provider.id) is not None
        assert storage2.get_provider(provider.id) is None
        assert len(storage1.list_providers()) == 1
        assert len(storage2.list_providers()) == 0

    def test_data_persists_within_instance(self) -> None:
        """Test que les données persistent dans la même instance."""
        storage = InMemoryStorage()

        from ai_engine.models.agent import Agent

        agent = Agent(name="Persistence Test", slug="persist", provider_id="test-provider")
        storage.save_agent(agent)

        # Faire quelques opérations
        agents = storage.list_agents()
        assert len(agents) == 1

        # Les données sont toujours là
        retrieved = storage.get_agent(agent.id)
        assert retrieved is not None
        assert retrieved.name == "Persistence Test"

    def test_transactions_are_noop(self) -> None:
        """Test que les transactions sont no-op pour InMemoryStorage."""
        storage = InMemoryStorage()

        from ai_engine.models.provider import LLMProviderConfig, ProviderType

        provider = LLMProviderConfig(
            name="tx-noop-test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
        )

        # Les transactions n'ont aucun effet sur InMemoryStorage
        # Les données sont toujours sauvées même si une exception est levée
        try:
            with storage.transaction():
                storage.save_provider(provider)
                raise Exception("This should not rollback in InMemoryStorage")
        except Exception:
            pass

        # Le provider devrait toujours être là car InMemoryStorage ne supporte pas les vraies transactions
        assert storage.get_provider(provider.id) is not None

    def test_close_is_noop(self) -> None:
        """Test que close() est no-op pour InMemoryStorage."""
        storage = InMemoryStorage()

        from ai_engine.models.agent import Agent

        agent = Agent(name="Close Test", slug="close", provider_id="test-provider")
        storage.save_agent(agent)

        # Close ne devrait rien faire
        storage.close()

        # Les données devraient toujours être accessibles
        assert storage.get_agent(agent.id) is not None
