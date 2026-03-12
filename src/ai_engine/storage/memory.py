"""
AI Engine — InMemoryStorage Backend.

Implémentation en mémoire du StorageBackend.
Parfait pour les tests unitaires et le prototypage rapide.

Usage:
    from ai_engine.storage import InMemoryStorage

    storage = InMemoryStorage()
    storage.save_provider(provider)
    provider = storage.get_provider("some-id")
"""

from __future__ import annotations

from datetime import UTC, datetime

from ai_engine.models.agent import Agent
from ai_engine.models.conversation import Conversation
from ai_engine.models.execution import Execution, ExecutionStep
from ai_engine.models.graph import Graph
from ai_engine.models.knowledge import KnowledgeSource
from ai_engine.models.memory import AgentMemory
from ai_engine.models.message import Message
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.models.skill import AgentSkillAssignment, Skill
from ai_engine.models.tool import ToolDefinition
from ai_engine.storage.base import StorageBackend
from ai_engine.types import AgentRole, ExecutionStatus, MemoryType


class InMemoryStorage(StorageBackend):
    """Storage en mémoire — idéal pour tests et prototypage.

    Toutes les données sont stockées dans des dicts Python.
    Aucune persistence sur disque — les données sont perdues à la fin du process.

    Usage:
        storage = InMemoryStorage()
        storage.save_agent(agent)
        found = storage.get_agent(agent.id)
    """

    def __init__(self) -> None:
        self._providers: dict[str, LLMProviderConfig] = {}
        self._agents: dict[str, Agent] = {}
        self._tools: dict[str, ToolDefinition] = {}
        self._skills: dict[str, Skill] = {}
        self._skill_assignments: dict[str, AgentSkillAssignment] = {}
        self._conversations: dict[str, Conversation] = {}
        self._messages: dict[str, Message] = {}
        self._executions: dict[str, Execution] = {}
        self._execution_steps: dict[str, ExecutionStep] = {}
        self._graphs: dict[str, Graph] = {}
        self._memories: dict[str, AgentMemory] = {}
        self._knowledge_sources: dict[str, KnowledgeSource] = {}

    # ──────────────────────────────────────────────
    # Providers
    # ──────────────────────────────────────────────

    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig:
        provider.updated_at = datetime.now(UTC)
        self._providers[provider.id] = provider
        return provider

    def get_provider(self, provider_id: str) -> LLMProviderConfig | None:
        return self._providers.get(provider_id)

    def get_provider_by_name(self, name: str) -> LLMProviderConfig | None:
        for provider in self._providers.values():
            if provider.name == name:
                return provider
        return None

    def list_providers(
        self, *, is_active: bool | None = None
    ) -> list[LLMProviderConfig]:
        results = list(self._providers.values())
        if is_active is not None:
            results = [p for p in results if p.is_active == is_active]
        return results

    def delete_provider(self, provider_id: str) -> bool:
        return self._providers.pop(provider_id, None) is not None

    # ──────────────────────────────────────────────
    # Agents
    # ──────────────────────────────────────────────

    def save_agent(self, agent: Agent) -> Agent:
        agent.updated_at = datetime.now(UTC)
        self._agents[agent.id] = agent
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def get_agent_by_slug(self, slug: str) -> Agent | None:
        for agent in self._agents.values():
            if agent.slug == slug:
                return agent
        return None

    def list_agents(
        self,
        *,
        owner_id: str | None = None,
        role: AgentRole | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        results = list(self._agents.values())
        if owner_id is not None:
            results = [a for a in results if a.owner_id == owner_id]
        if role is not None:
            results = [a for a in results if a.role == role]
        if is_active is not None:
            results = [a for a in results if a.is_active == is_active]
        return results

    def delete_agent(self, agent_id: str) -> bool:
        return self._agents.pop(agent_id, None) is not None

    # ──────────────────────────────────────────────
    # Tools
    # ──────────────────────────────────────────────

    def save_tool(self, tool: ToolDefinition) -> ToolDefinition:
        tool.updated_at = datetime.now(UTC)
        self._tools[tool.id] = tool
        return tool

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id)

    def get_tool_by_key(self, key: str) -> ToolDefinition | None:
        for tool in self._tools.values():
            if tool.key == key:
                return tool
        return None

    def list_tools(self, *, is_active: bool | None = None) -> list[ToolDefinition]:
        results = list(self._tools.values())
        if is_active is not None:
            results = [t for t in results if t.is_active == is_active]
        return results

    def list_tools_for_agent(self, agent_id: str) -> list[ToolDefinition]:
        agent = self.get_agent(agent_id)
        if agent is None:
            return []
        return [
            tool
            for tool_id in agent.tool_ids
            if (tool := self._tools.get(tool_id)) is not None
        ]

    def delete_tool(self, tool_id: str) -> bool:
        return self._tools.pop(tool_id, None) is not None

    # ──────────────────────────────────────────────
    # Skills
    # ──────────────────────────────────────────────

    def save_skill(self, skill: Skill) -> Skill:
        skill.updated_at = datetime.now(UTC)
        self._skills[skill.id] = skill
        return skill

    def get_skill(self, skill_id: str) -> Skill | None:
        return self._skills.get(skill_id)

    def list_skills(self, *, is_active: bool | None = None) -> list[Skill]:
        results = list(self._skills.values())
        if is_active is not None:
            results = [s for s in results if s.is_active == is_active]
        return results

    def save_skill_assignment(
        self, assignment: AgentSkillAssignment
    ) -> AgentSkillAssignment:
        assignment.updated_at = datetime.now(UTC)
        self._skill_assignments[assignment.id] = assignment
        return assignment

    def list_skill_assignments_for_agent(
        self, agent_id: str
    ) -> list[AgentSkillAssignment]:
        return [a for a in self._skill_assignments.values() if a.agent_id == agent_id]

    def delete_skill(self, skill_id: str) -> bool:
        return self._skills.pop(skill_id, None) is not None

    # ──────────────────────────────────────────────
    # Conversations
    # ──────────────────────────────────────────────

    def save_conversation(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = datetime.now(UTC)
        self._conversations[conversation.id] = conversation
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        return self._conversations.get(conversation_id)

    def list_conversations(
        self,
        *,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Conversation]:
        results = list(self._conversations.values())
        if agent_id is not None:
            results = [c for c in results if c.agent_id == agent_id]
        if owner_id is not None:
            results = [c for c in results if c.owner_id == owner_id]
        return results

    def delete_conversation(self, conversation_id: str) -> bool:
        return self._conversations.pop(conversation_id, None) is not None

    # ──────────────────────────────────────────────
    # Messages
    # ──────────────────────────────────────────────

    def save_message(self, message: Message) -> Message:
        self._messages[message.id] = message
        return message

    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        results = sorted(
            (
                m
                for m in self._messages.values()
                if m.conversation_id == conversation_id
            ),
            key=lambda m: m.created_at,
        )
        results = results[offset:]
        if limit is not None:
            results = results[:limit]
        return results

    def count_messages(self, conversation_id: str) -> int:
        return sum(
            1 for m in self._messages.values() if m.conversation_id == conversation_id
        )

    # ──────────────────────────────────────────────
    # Executions
    # ──────────────────────────────────────────────

    def save_execution(self, execution: Execution) -> Execution:
        execution.updated_at = datetime.now(UTC)
        self._executions[execution.id] = execution
        return execution

    def get_execution(self, execution_id: str) -> Execution | None:
        return self._executions.get(execution_id)

    def list_executions(
        self,
        *,
        agent_id: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> list[Execution]:
        results = list(self._executions.values())
        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]
        if status is not None:
            results = [e for e in results if e.status == status]
        return results

    def save_execution_step(self, step: ExecutionStep) -> ExecutionStep:
        self._execution_steps[step.id] = step
        return step

    def get_execution_steps(self, execution_id: str) -> list[ExecutionStep]:
        results = [
            s for s in self._execution_steps.values() if s.execution_id == execution_id
        ]
        return sorted(results, key=lambda s: s.order)

    # ──────────────────────────────────────────────
    # Graphs
    # ──────────────────────────────────────────────

    def save_graph(self, graph: Graph) -> Graph:
        graph.updated_at = datetime.now(UTC)
        self._graphs[graph.id] = graph
        return graph

    def get_graph(self, graph_id: str) -> Graph | None:
        return self._graphs.get(graph_id)

    def get_graph_by_slug(self, slug: str) -> Graph | None:
        for graph in self._graphs.values():
            if graph.slug == slug:
                return graph
        return None

    def list_graphs(
        self,
        *,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Graph]:
        results = list(self._graphs.values())
        if agent_id is not None:
            results = [g for g in results if g.agent_id == agent_id]
        if owner_id is not None:
            results = [g for g in results if g.owner_id == owner_id]
        return results

    def delete_graph(self, graph_id: str) -> bool:
        return self._graphs.pop(graph_id, None) is not None

    # ──────────────────────────────────────────────
    # Memory
    # ──────────────────────────────────────────────

    def save_memory(self, memory: AgentMemory) -> AgentMemory:
        memory.updated_at = datetime.now(UTC)
        self._memories[memory.id] = memory
        return memory

    def get_memory(self, agent_id: str, key: str) -> AgentMemory | None:
        for memory in self._memories.values():
            if memory.agent_id == agent_id and memory.key == key:
                return memory
        return None

    def list_memories(
        self,
        agent_id: str,
        *,
        memory_type: MemoryType | None = None,
    ) -> list[AgentMemory]:
        results = [m for m in self._memories.values() if m.agent_id == agent_id]
        if memory_type is not None:
            results = [m for m in results if m.memory_type == memory_type]
        return results

    def delete_memory(self, memory_id: str) -> bool:
        return self._memories.pop(memory_id, None) is not None

    def delete_expired_memories(self) -> int:
        now = datetime.now(UTC)
        expired_ids = [
            m.id
            for m in self._memories.values()
            if m.expires_at is not None and now >= m.expires_at
        ]
        for mid in expired_ids:
            del self._memories[mid]
        return len(expired_ids)

    # ──────────────────────────────────────────────
    # Knowledge
    # ──────────────────────────────────────────────

    def save_knowledge_source(self, source: KnowledgeSource) -> KnowledgeSource:
        source.updated_at = datetime.now(UTC)
        self._knowledge_sources[source.id] = source
        return source

    def get_knowledge_source(self, source_id: str) -> KnowledgeSource | None:
        return self._knowledge_sources.get(source_id)

    def list_knowledge_sources(
        self,
        *,
        agent_id: str | None = None,
    ) -> list[KnowledgeSource]:
        results = list(self._knowledge_sources.values())
        if agent_id is not None:
            results = [s for s in results if agent_id in s.agent_ids]
        return results

    def delete_knowledge_source(self, source_id: str) -> bool:
        return self._knowledge_sources.pop(source_id, None) is not None
