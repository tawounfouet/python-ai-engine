"""
AI Engine Django Adapter — DjangoORMStorage.

Implémente StorageBackend en persistant les domain-models ai_engine
dans la base de données Django via l'ORM.

Stratégie de stockage :
  Chaque entité est stockée dans une table Django dédiée.
  La ligne contient les colonnes indexées (id, slug, agent_id, …)
  + une colonne `data` (JSONField) qui stocke le Pydantic model sérialisé.

  Cette approche évite une migration complexe par champ et reste
  parfaitement requêtable via le JSONField de Django.

Utilisation :
    from ai_engine.adapters.django import DjangoORMStorage
    from ai_engine.services import AgentService

    storage = DjangoORMStorage()
    svc = AgentService(storage)
    agent = svc.create_agent(name="Bot", provider_id="...", system_prompt="...")
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from ai_engine.models.agent import Agent
from ai_engine.models.conversation import Conversation
from ai_engine.models.message import Message
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.storage.base import StorageBackend
from ai_engine.types import AgentRole

if TYPE_CHECKING:
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class DjangoORMStorage(StorageBackend):
    """
    StorageBackend Django ORM.

    Chaque méthode traduit un appel ai_engine en QuerySet Django,
    puis désérialise le JSON stocké en domain-model Pydantic.

    Les modèles Django sont importés lazily (dans chaque méthode) pour
    éviter les AppRegistryNotReady errors lors de l'import du module.
    """

    # ──────────────────────────────────────────────────────────────────────────
    # Providers
    # ──────────────────────────────────────────────────────────────────────────

    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig:
        from ai_engine.adapters.django.orm_models import ProviderRecord

        provider.updated_at = _now()
        ProviderRecord.objects.update_or_create(
            id=provider.id,
            defaults={
                "name": provider.name,
                "provider_type": provider.provider_type,
                "is_active": provider.is_active,
                "data": provider.model_dump(mode="json"),
            },
        )
        return provider

    def get_provider(self, provider_id: str) -> LLMProviderConfig | None:
        from ai_engine.adapters.django.orm_models import ProviderRecord

        try:
            record = ProviderRecord.objects.get(id=provider_id)
        except ProviderRecord.DoesNotExist:
            return None
        return LLMProviderConfig.model_validate(record.data)

    def get_provider_by_name(self, name: str) -> LLMProviderConfig | None:
        from ai_engine.adapters.django.orm_models import ProviderRecord

        record = ProviderRecord.objects.filter(name=name).first()
        if not record:
            return None
        return LLMProviderConfig.model_validate(record.data)

    def list_providers(
        self, *, is_active: bool | None = None
    ) -> list[LLMProviderConfig]:
        from ai_engine.adapters.django.orm_models import ProviderRecord

        qs = ProviderRecord.objects.all()
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        return [LLMProviderConfig.model_validate(r.data) for r in qs]

    def delete_provider(self, provider_id: str) -> bool:
        from ai_engine.adapters.django.orm_models import ProviderRecord

        deleted, _ = ProviderRecord.objects.filter(id=provider_id).delete()
        return deleted > 0

    # ──────────────────────────────────────────────────────────────────────────
    # Agents
    # ──────────────────────────────────────────────────────────────────────────

    def save_agent(self, agent: Agent) -> Agent:
        from ai_engine.adapters.django.orm_models import AgentRecord

        agent.updated_at = _now()
        AgentRecord.objects.update_or_create(
            id=agent.id,
            defaults={
                "name": agent.name,
                "slug": agent.slug,
                "provider_id": agent.provider_id,
                "role": agent.role,
                "is_active": agent.is_active,
                "data": agent.model_dump(mode="json"),
            },
        )
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        from ai_engine.adapters.django.orm_models import AgentRecord

        try:
            record = AgentRecord.objects.get(id=agent_id)
        except AgentRecord.DoesNotExist:
            return None
        return Agent.model_validate(record.data)

    def get_agent_by_slug(self, slug: str) -> Agent | None:
        from ai_engine.adapters.django.orm_models import AgentRecord

        record = AgentRecord.objects.filter(slug=slug).first()
        if not record:
            return None
        return Agent.model_validate(record.data)

    def list_agents(
        self,
        *,
        owner_id: str | None = None,
        role: AgentRole | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        from ai_engine.adapters.django.orm_models import AgentRecord

        qs = AgentRecord.objects.all()
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        if role is not None:
            qs = qs.filter(role=str(role))
        return [Agent.model_validate(r.data) for r in qs]

    def delete_agent(self, agent_id: str) -> bool:
        from ai_engine.adapters.django.orm_models import AgentRecord

        deleted, _ = AgentRecord.objects.filter(id=agent_id).delete()
        return deleted > 0

    # ──────────────────────────────────────────────────────────────────────────
    # Conversations
    # ──────────────────────────────────────────────────────────────────────────

    def save_conversation(self, conversation: Conversation) -> Conversation:
        from ai_engine.adapters.django.orm_models import ConversationRecord

        conversation.updated_at = _now()
        ConversationRecord.objects.update_or_create(
            id=conversation.id,
            defaults={
                "agent_id": conversation.agent_id,
                "title": conversation.title or "",
                "data": conversation.model_dump(mode="json"),
            },
        )
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        from ai_engine.adapters.django.orm_models import ConversationRecord

        try:
            record = ConversationRecord.objects.get(id=conversation_id)
        except ConversationRecord.DoesNotExist:
            return None
        return Conversation.model_validate(record.data)

    def list_conversations(
        self,
        *,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Conversation]:
        from ai_engine.adapters.django.orm_models import ConversationRecord

        qs = ConversationRecord.objects.all()
        if agent_id is not None:
            qs = qs.filter(agent_id=agent_id)
        return [Conversation.model_validate(r.data) for r in qs.order_by("-id")]

    def delete_conversation(self, conversation_id: str) -> bool:
        from ai_engine.adapters.django.orm_models import ConversationRecord

        deleted, _ = ConversationRecord.objects.filter(id=conversation_id).delete()
        return deleted > 0

    # ──────────────────────────────────────────────────────────────────────────
    # Messages
    # ──────────────────────────────────────────────────────────────────────────

    def save_message(self, message: Message) -> Message:
        from ai_engine.adapters.django.orm_models import MessageRecord

        MessageRecord.objects.update_or_create(
            id=message.id,
            defaults={
                "conversation_id": message.conversation_id,
                "role": message.role,
                "data": message.model_dump(mode="json"),
            },
        )
        return message

    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        from ai_engine.adapters.django.orm_models import MessageRecord

        qs = MessageRecord.objects.filter(conversation_id=conversation_id).order_by(
            "created_at"
        )
        qs = qs[offset:]
        if limit is not None:
            qs = qs[:limit]
        return [Message.model_validate(r.data) for r in qs]

    def count_messages(self, conversation_id: str) -> int:
        from ai_engine.adapters.django.orm_models import MessageRecord

        return MessageRecord.objects.filter(conversation_id=conversation_id).count()

    # ── Tools (stubs — not persisted via ORM yet) ──────────────────────────

    def save_tool(self, tool):  # type: ignore[override]
        raise NotImplementedError("Tool ORM persistence not yet implemented.")

    def get_tool(self, tool_id: str):  # type: ignore[override]
        return None

    def get_tool_by_key(self, key: str):  # type: ignore[override]
        return None

    def list_tools(self, *, is_active=None) -> list:  # type: ignore[override]
        return []

    def list_tools_for_agent(self, agent_id: str) -> list:  # type: ignore[override]
        return []

    def delete_tool(self, tool_id: str) -> bool:  # type: ignore[override]
        return False

    # ── Skills (stubs) ─────────────────────────────────────────────────────

    def save_skill(self, skill):  # type: ignore[override]
        raise NotImplementedError("Skill ORM persistence not yet implemented.")

    def get_skill(self, skill_id: str):  # type: ignore[override]
        return None

    def list_skills(self, *, is_active=None) -> list:  # type: ignore[override]
        return []

    def save_skill_assignment(self, assignment):  # type: ignore[override]
        raise NotImplementedError

    def list_skill_assignments_for_agent(self, agent_id: str) -> list:  # type: ignore[override]
        return []

    def delete_skill(self, skill_id: str) -> bool:  # type: ignore[override]
        return False

    # ── Executions (stubs) ─────────────────────────────────────────────────

    def save_execution(self, execution):  # type: ignore[override]
        raise NotImplementedError

    def get_execution(self, execution_id: str):  # type: ignore[override]
        return None

    def list_executions(self, *, agent_id=None, status=None) -> list:  # type: ignore[override]
        return []

    def save_execution_step(self, step):  # type: ignore[override]
        raise NotImplementedError

    def get_execution_steps(self, execution_id: str) -> list:  # type: ignore[override]
        return []

    # ── Graphs (stubs) ─────────────────────────────────────────────────────

    def save_graph(self, graph):  # type: ignore[override]
        raise NotImplementedError

    def get_graph(self, graph_id: str):  # type: ignore[override]
        return None

    def get_graph_by_slug(self, slug: str):  # type: ignore[override]
        return None

    def list_graphs(self, *, agent_id=None, owner_id=None) -> list:  # type: ignore[override]
        return []

    def delete_graph(self, graph_id: str) -> bool:  # type: ignore[override]
        return False

    # ── Memory (stubs) ─────────────────────────────────────────────────────

    def save_memory(self, memory):  # type: ignore[override]
        raise NotImplementedError

    def get_memory(self, agent_id: str, key: str):  # type: ignore[override]
        return None

    def list_memories(self, agent_id: str, *, memory_type=None) -> list:  # type: ignore[override]
        return []

    def delete_memory(self, memory_id: str) -> bool:  # type: ignore[override]
        return False

    def delete_expired_memories(self) -> int:  # type: ignore[override]
        return 0

    # ── Knowledge (stubs) ──────────────────────────────────────────────────

    def save_knowledge_source(self, source):  # type: ignore[override]
        raise NotImplementedError

    def get_knowledge_source(self, source_id: str):  # type: ignore[override]
        return None

    def list_knowledge_sources(self, *, agent_id=None) -> list:  # type: ignore[override]
        return []

    def delete_knowledge_source(self, source_id: str) -> bool:  # type: ignore[override]
        return False
