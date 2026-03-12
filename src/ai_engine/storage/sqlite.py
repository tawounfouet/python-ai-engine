"""
AI Engine — SQLiteStorage Backend.

Implémentation SQLite du StorageBackend.
Zero-config, fichier unique, parfait pour CLI/scripts/notebooks.

Stratégie : chaque entité est stockée comme JSON sérialisé dans une colonne `data`,
avec des colonnes indexées pour les requêtes fréquentes (id, slug, agent_id, etc.).
Cela combine la flexibilité du schemaless avec la rapidité des index SQL.

Usage:
    from ai_engine.storage import SQLiteStorage

    storage = SQLiteStorage("my_project.db")
    storage.save_provider(provider)

    # Ou en mode mémoire pour les tests :
    storage = SQLiteStorage(":memory:")
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
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


def _serialize(model: object) -> str:
    """Sérialise un Pydantic model en JSON string."""
    if hasattr(model, "model_dump_json"):
        return model.model_dump_json()  # type: ignore[union-attr]
    return json.dumps(model)  # type: ignore[arg-type]


class SQLiteStorage(StorageBackend):
    """Storage SQLite — zero-config, fichier unique, parfait pour CLI/scripts.

    Chaque entité est stockée comme JSON sérialisé dans une colonne `data`,
    avec des colonnes indexées pour les requêtes fréquentes.

    Args:
        db_path: Chemin vers le fichier SQLite. Utiliser ":memory:" pour un
                 storage en mémoire (utile pour les tests).

    Usage:
        storage = SQLiteStorage("ai_engine.db")
        storage.save_agent(agent)

        # Context manager :
        with SQLiteStorage("ai_engine.db") as storage:
            storage.save_agent(agent)
    """

    def __init__(self, db_path: str = "ai_engine.db") -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        """Crée les tables si elles n'existent pas."""
        statements = [
            """CREATE TABLE IF NOT EXISTS providers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_providers_name ON providers (name)",
            """CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL DEFAULT '',
                owner_id TEXT,
                role TEXT NOT NULL DEFAULT 'assistant',
                is_active INTEGER NOT NULL DEFAULT 1,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_agents_slug ON agents (slug)",
            "CREATE INDEX IF NOT EXISTS idx_agents_owner ON agents (owner_id)",
            """CREATE TABLE IF NOT EXISTS tools (
                id TEXT PRIMARY KEY,
                key TEXT NOT NULL DEFAULT '',
                is_active INTEGER NOT NULL DEFAULT 1,
                data TEXT NOT NULL
            )""",
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_tools_key ON tools (key)",
            """CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                is_active INTEGER NOT NULL DEFAULT 1,
                data TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS skill_assignments (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                skill_id TEXT NOT NULL,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_skill_assignments_agent ON skill_assignments (agent_id)",
            """CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                owner_id TEXT,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations (agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_conversations_owner ON conversations (owner_id)",
            """CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages (conversation_id, created_at)",
            """CREATE TABLE IF NOT EXISTS executions (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_executions_agent ON executions (agent_id)",
            "CREATE INDEX IF NOT EXISTS idx_executions_status ON executions (status)",
            """CREATE TABLE IF NOT EXISTS execution_steps (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                step_order INTEGER NOT NULL DEFAULT 0,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_execution_steps_exec ON execution_steps (execution_id, step_order)",
            """CREATE TABLE IF NOT EXISTS graphs (
                id TEXT PRIMARY KEY,
                slug TEXT NOT NULL DEFAULT '',
                agent_id TEXT NOT NULL,
                owner_id TEXT,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_graphs_slug ON graphs (slug)",
            "CREATE INDEX IF NOT EXISTS idx_graphs_agent ON graphs (agent_id)",
            """CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                key TEXT NOT NULL,
                memory_type TEXT NOT NULL DEFAULT 'long_term',
                expires_at TEXT,
                data TEXT NOT NULL
            )""",
            "CREATE INDEX IF NOT EXISTS idx_memories_agent_key ON memories (agent_id, key)",
            """CREATE TABLE IF NOT EXISTS knowledge_sources (
                id TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS knowledge_source_agents (
                source_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                PRIMARY KEY (source_id, agent_id)
            )""",
            "CREATE INDEX IF NOT EXISTS idx_ks_agents ON knowledge_source_agents (agent_id)",
        ]
        for stmt in statements:
            self._conn.execute(stmt)
        self._conn.commit()

    # ──────────────────────────────────────────────
    # Providers
    # ──────────────────────────────────────────────

    def save_provider(self, provider: LLMProviderConfig) -> LLMProviderConfig:
        provider.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO providers (id, name, is_active, data) VALUES (?, ?, ?, ?)",
            (provider.id, provider.name, int(provider.is_active), _serialize(provider)),
        )
        self._conn.commit()
        return provider

    def get_provider(self, provider_id: str) -> LLMProviderConfig | None:
        row = self._conn.execute(
            "SELECT data FROM providers WHERE id = ?", (provider_id,)
        ).fetchone()
        if row is None:
            return None
        return LLMProviderConfig.model_validate_json(row["data"])

    def get_provider_by_name(self, name: str) -> LLMProviderConfig | None:
        row = self._conn.execute(
            "SELECT data FROM providers WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None
        return LLMProviderConfig.model_validate_json(row["data"])

    def list_providers(
        self, *, is_active: bool | None = None
    ) -> list[LLMProviderConfig]:
        if is_active is not None:
            rows = self._conn.execute(
                "SELECT data FROM providers WHERE is_active = ?", (int(is_active),)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM providers").fetchall()
        return [LLMProviderConfig.model_validate_json(r["data"]) for r in rows]

    def delete_provider(self, provider_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM providers WHERE id = ?", (provider_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Agents
    # ──────────────────────────────────────────────

    def save_agent(self, agent: Agent) -> Agent:
        agent.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO agents (id, slug, owner_id, role, is_active, data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                agent.id,
                agent.slug,
                agent.owner_id,
                str(agent.role),
                int(agent.is_active),
                _serialize(agent),
            ),
        )
        self._conn.commit()
        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        row = self._conn.execute(
            "SELECT data FROM agents WHERE id = ?", (agent_id,)
        ).fetchone()
        if row is None:
            return None
        return Agent.model_validate_json(row["data"])

    def get_agent_by_slug(self, slug: str) -> Agent | None:
        row = self._conn.execute(
            "SELECT data FROM agents WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            return None
        return Agent.model_validate_json(row["data"])

    def list_agents(
        self,
        *,
        owner_id: str | None = None,
        role: AgentRole | None = None,
        is_active: bool | None = None,
    ) -> list[Agent]:
        conditions: list[str] = []
        params: list[object] = []
        if owner_id is not None:
            conditions.append("owner_id = ?")
            params.append(owner_id)
        if role is not None:
            conditions.append("role = ?")
            params.append(str(role))
        if is_active is not None:
            conditions.append("is_active = ?")
            params.append(int(is_active))
        query = "SELECT data FROM agents"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        rows = self._conn.execute(query, params).fetchall()
        return [Agent.model_validate_json(r["data"]) for r in rows]

    def delete_agent(self, agent_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Tools
    # ──────────────────────────────────────────────

    def save_tool(self, tool: ToolDefinition) -> ToolDefinition:
        tool.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO tools (id, key, is_active, data) VALUES (?, ?, ?, ?)",
            (tool.id, tool.key, int(tool.is_active), _serialize(tool)),
        )
        self._conn.commit()
        return tool

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        row = self._conn.execute(
            "SELECT data FROM tools WHERE id = ?", (tool_id,)
        ).fetchone()
        if row is None:
            return None
        return ToolDefinition.model_validate_json(row["data"])

    def get_tool_by_key(self, key: str) -> ToolDefinition | None:
        row = self._conn.execute(
            "SELECT data FROM tools WHERE key = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return ToolDefinition.model_validate_json(row["data"])

    def list_tools(self, *, is_active: bool | None = None) -> list[ToolDefinition]:
        if is_active is not None:
            rows = self._conn.execute(
                "SELECT data FROM tools WHERE is_active = ?", (int(is_active),)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM tools").fetchall()
        return [ToolDefinition.model_validate_json(r["data"]) for r in rows]

    def list_tools_for_agent(self, agent_id: str) -> list[ToolDefinition]:
        agent = self.get_agent(agent_id)
        if agent is None or not agent.tool_ids:
            return []
        placeholders = ",".join("?" for _ in agent.tool_ids)
        rows = self._conn.execute(
            f"SELECT data FROM tools WHERE id IN ({placeholders})",  # noqa: S608
            agent.tool_ids,
        ).fetchall()
        return [ToolDefinition.model_validate_json(r["data"]) for r in rows]

    def delete_tool(self, tool_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM tools WHERE id = ?", (tool_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Skills
    # ──────────────────────────────────────────────

    def save_skill(self, skill: Skill) -> Skill:
        skill.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO skills (id, is_active, data) VALUES (?, ?, ?)",
            (skill.id, int(skill.is_active), _serialize(skill)),
        )
        self._conn.commit()
        return skill

    def get_skill(self, skill_id: str) -> Skill | None:
        row = self._conn.execute(
            "SELECT data FROM skills WHERE id = ?", (skill_id,)
        ).fetchone()
        if row is None:
            return None
        return Skill.model_validate_json(row["data"])

    def list_skills(self, *, is_active: bool | None = None) -> list[Skill]:
        if is_active is not None:
            rows = self._conn.execute(
                "SELECT data FROM skills WHERE is_active = ?", (int(is_active),)
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM skills").fetchall()
        return [Skill.model_validate_json(r["data"]) for r in rows]

    def save_skill_assignment(
        self, assignment: AgentSkillAssignment
    ) -> AgentSkillAssignment:
        assignment.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO skill_assignments (id, agent_id, skill_id, data) VALUES (?, ?, ?, ?)",
            (
                assignment.id,
                assignment.agent_id,
                assignment.skill_id,
                _serialize(assignment),
            ),
        )
        self._conn.commit()
        return assignment

    def list_skill_assignments_for_agent(
        self, agent_id: str
    ) -> list[AgentSkillAssignment]:
        rows = self._conn.execute(
            "SELECT data FROM skill_assignments WHERE agent_id = ?", (agent_id,)
        ).fetchall()
        return [AgentSkillAssignment.model_validate_json(r["data"]) for r in rows]

    def delete_skill(self, skill_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM skills WHERE id = ?", (skill_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Conversations
    # ──────────────────────────────────────────────

    def save_conversation(self, conversation: Conversation) -> Conversation:
        conversation.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO conversations (id, agent_id, owner_id, data) VALUES (?, ?, ?, ?)",
            (
                conversation.id,
                conversation.agent_id,
                conversation.owner_id,
                _serialize(conversation),
            ),
        )
        self._conn.commit()
        return conversation

    def get_conversation(self, conversation_id: str) -> Conversation | None:
        row = self._conn.execute(
            "SELECT data FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if row is None:
            return None
        return Conversation.model_validate_json(row["data"])

    def list_conversations(
        self,
        *,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Conversation]:
        conditions: list[str] = []
        params: list[object] = []
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if owner_id is not None:
            conditions.append("owner_id = ?")
            params.append(owner_id)
        query = "SELECT data FROM conversations"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        rows = self._conn.execute(query, params).fetchall()
        return [Conversation.model_validate_json(r["data"]) for r in rows]

    def delete_conversation(self, conversation_id: str) -> bool:
        cursor = self._conn.execute(
            "DELETE FROM conversations WHERE id = ?", (conversation_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Messages
    # ──────────────────────────────────────────────

    def save_message(self, message: Message) -> Message:
        self._conn.execute(
            "INSERT OR REPLACE INTO messages (id, conversation_id, created_at, data) VALUES (?, ?, ?, ?)",
            (
                message.id,
                message.conversation_id,
                message.created_at.isoformat(),
                _serialize(message),
            ),
        )
        self._conn.commit()
        return message

    def get_messages(
        self,
        conversation_id: str,
        *,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Message]:
        query = "SELECT data FROM messages WHERE conversation_id = ? ORDER BY created_at ASC"
        params: list[object] = [conversation_id]
        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        elif offset > 0:
            query += " LIMIT -1 OFFSET ?"
            params.append(offset)
        rows = self._conn.execute(query, params).fetchall()
        return [Message.model_validate_json(r["data"]) for r in rows]

    def count_messages(self, conversation_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    # ──────────────────────────────────────────────
    # Executions
    # ──────────────────────────────────────────────

    def save_execution(self, execution: Execution) -> Execution:
        execution.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO executions (id, agent_id, status, data) VALUES (?, ?, ?, ?)",
            (
                execution.id,
                execution.agent_id,
                str(execution.status),
                _serialize(execution),
            ),
        )
        self._conn.commit()
        return execution

    def get_execution(self, execution_id: str) -> Execution | None:
        row = self._conn.execute(
            "SELECT data FROM executions WHERE id = ?", (execution_id,)
        ).fetchone()
        if row is None:
            return None
        return Execution.model_validate_json(row["data"])

    def list_executions(
        self,
        *,
        agent_id: str | None = None,
        status: ExecutionStatus | None = None,
    ) -> list[Execution]:
        conditions: list[str] = []
        params: list[object] = []
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if status is not None:
            conditions.append("status = ?")
            params.append(str(status))
        query = "SELECT data FROM executions"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        rows = self._conn.execute(query, params).fetchall()
        return [Execution.model_validate_json(r["data"]) for r in rows]

    def save_execution_step(self, step: ExecutionStep) -> ExecutionStep:
        self._conn.execute(
            "INSERT OR REPLACE INTO execution_steps (id, execution_id, step_order, data) VALUES (?, ?, ?, ?)",
            (step.id, step.execution_id, step.order, _serialize(step)),
        )
        self._conn.commit()
        return step

    def get_execution_steps(self, execution_id: str) -> list[ExecutionStep]:
        rows = self._conn.execute(
            "SELECT data FROM execution_steps WHERE execution_id = ? ORDER BY step_order ASC",
            (execution_id,),
        ).fetchall()
        return [ExecutionStep.model_validate_json(r["data"]) for r in rows]

    # ──────────────────────────────────────────────
    # Graphs
    # ──────────────────────────────────────────────

    def save_graph(self, graph: Graph) -> Graph:
        graph.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO graphs (id, slug, agent_id, owner_id, data) VALUES (?, ?, ?, ?, ?)",
            (graph.id, graph.slug, graph.agent_id, graph.owner_id, _serialize(graph)),
        )
        self._conn.commit()
        return graph

    def get_graph(self, graph_id: str) -> Graph | None:
        row = self._conn.execute(
            "SELECT data FROM graphs WHERE id = ?", (graph_id,)
        ).fetchone()
        if row is None:
            return None
        return Graph.model_validate_json(row["data"])

    def get_graph_by_slug(self, slug: str) -> Graph | None:
        row = self._conn.execute(
            "SELECT data FROM graphs WHERE slug = ?", (slug,)
        ).fetchone()
        if row is None:
            return None
        return Graph.model_validate_json(row["data"])

    def list_graphs(
        self,
        *,
        agent_id: str | None = None,
        owner_id: str | None = None,
    ) -> list[Graph]:
        conditions: list[str] = []
        params: list[object] = []
        if agent_id is not None:
            conditions.append("agent_id = ?")
            params.append(agent_id)
        if owner_id is not None:
            conditions.append("owner_id = ?")
            params.append(owner_id)
        query = "SELECT data FROM graphs"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        rows = self._conn.execute(query, params).fetchall()
        return [Graph.model_validate_json(r["data"]) for r in rows]

    def delete_graph(self, graph_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM graphs WHERE id = ?", (graph_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Memory
    # ──────────────────────────────────────────────

    def save_memory(self, memory: AgentMemory) -> AgentMemory:
        memory.updated_at = datetime.now(UTC)
        expires_at_str = memory.expires_at.isoformat() if memory.expires_at else None
        self._conn.execute(
            "INSERT OR REPLACE INTO memories (id, agent_id, key, memory_type, expires_at, data) VALUES (?, ?, ?, ?, ?, ?)",
            (
                memory.id,
                memory.agent_id,
                memory.key,
                str(memory.memory_type),
                expires_at_str,
                _serialize(memory),
            ),
        )
        self._conn.commit()
        return memory

    def get_memory(self, agent_id: str, key: str) -> AgentMemory | None:
        row = self._conn.execute(
            "SELECT data FROM memories WHERE agent_id = ? AND key = ?",
            (agent_id, key),
        ).fetchone()
        if row is None:
            return None
        return AgentMemory.model_validate_json(row["data"])

    def list_memories(
        self,
        agent_id: str,
        *,
        memory_type: MemoryType | None = None,
    ) -> list[AgentMemory]:
        if memory_type is not None:
            rows = self._conn.execute(
                "SELECT data FROM memories WHERE agent_id = ? AND memory_type = ?",
                (agent_id, str(memory_type)),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT data FROM memories WHERE agent_id = ?", (agent_id,)
            ).fetchall()
        return [AgentMemory.model_validate_json(r["data"]) for r in rows]

    def delete_memory(self, memory_id: str) -> bool:
        cursor = self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def delete_expired_memories(self) -> int:
        now = datetime.now(UTC).isoformat()
        cursor = self._conn.execute(
            "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at <= ?",
            (now,),
        )
        self._conn.commit()
        return cursor.rowcount

    # ──────────────────────────────────────────────
    # Knowledge
    # ──────────────────────────────────────────────

    def save_knowledge_source(self, source: KnowledgeSource) -> KnowledgeSource:
        source.updated_at = datetime.now(UTC)
        self._conn.execute(
            "INSERT OR REPLACE INTO knowledge_sources (id, data) VALUES (?, ?)",
            (source.id, _serialize(source)),
        )
        # Update agent associations
        self._conn.execute(
            "DELETE FROM knowledge_source_agents WHERE source_id = ?", (source.id,)
        )
        for agent_id in source.agent_ids:
            self._conn.execute(
                "INSERT INTO knowledge_source_agents (source_id, agent_id) VALUES (?, ?)",
                (source.id, agent_id),
            )
        self._conn.commit()
        return source

    def get_knowledge_source(self, source_id: str) -> KnowledgeSource | None:
        row = self._conn.execute(
            "SELECT data FROM knowledge_sources WHERE id = ?", (source_id,)
        ).fetchone()
        if row is None:
            return None
        return KnowledgeSource.model_validate_json(row["data"])

    def list_knowledge_sources(
        self,
        *,
        agent_id: str | None = None,
    ) -> list[KnowledgeSource]:
        if agent_id is not None:
            rows = self._conn.execute(
                """SELECT ks.data FROM knowledge_sources ks
                   JOIN knowledge_source_agents ksa ON ks.id = ksa.source_id
                   WHERE ksa.agent_id = ?""",
                (agent_id,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT data FROM knowledge_sources").fetchall()
        return [KnowledgeSource.model_validate_json(r["data"]) for r in rows]

    def delete_knowledge_source(self, source_id: str) -> bool:
        self._conn.execute(
            "DELETE FROM knowledge_source_agents WHERE source_id = ?", (source_id,)
        )
        cursor = self._conn.execute(
            "DELETE FROM knowledge_sources WHERE id = ?", (source_id,)
        )
        self._conn.commit()
        return cursor.rowcount > 0

    # ──────────────────────────────────────────────
    # Transaction support
    # ──────────────────────────────────────────────

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Transaction SQLite — rollback automatique en cas d'erreur."""
        self._conn.execute("BEGIN")
        try:
            yield
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ──────────────────────────────────────────────
    # Context manager support
    # ──────────────────────────────────────────────

    def __enter__(self) -> SQLiteStorage:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # ──────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────

    def close(self) -> None:
        """Ferme la connexion SQLite."""
        self._conn.close()
