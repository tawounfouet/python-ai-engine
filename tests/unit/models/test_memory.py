"""Tests unitaires pour ai_engine.models.memory."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ai_engine import AgentMemory, MemoryType


class TestAgentMemory:
    def test_creation_minimal(self) -> None:
        memory = AgentMemory(
            agent_id="agent-1",
            key="user_prefs",
            content="likes python",
        )
        assert memory.agent_id == "agent-1"
        assert memory.key == "user_prefs"
        assert memory.content == "likes python"
        assert memory.memory_type == MemoryType.LONG_TERM
        assert memory.embedding is None
        assert memory.relevance_score == 1.0
        assert memory.expires_at is None
        assert memory.metadata == {}

    def test_creation_full(self) -> None:
        expires = datetime.now(UTC) + timedelta(hours=1)
        memory = AgentMemory(
            agent_id="agent-1",
            key="last_research",
            content='{"topic": "quantum computing", "summary": "..."}',
            memory_type=MemoryType.SHORT_TERM,
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5],
            relevance_score=0.85,
            metadata={"source": "execution-123"},
            expires_at=expires,
        )
        assert memory.memory_type == MemoryType.SHORT_TERM
        assert memory.embedding is not None
        assert len(memory.embedding) == 5
        assert memory.relevance_score == 0.85
        assert memory.expires_at == expires

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            AgentMemory(key="k", content="c")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            AgentMemory(agent_id="a", content="c")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            AgentMemory(agent_id="a", key="k")  # type: ignore[call-arg]

    def test_relevance_score_bounds(self) -> None:
        AgentMemory(agent_id="a", key="k", content="c", relevance_score=0.0)
        AgentMemory(agent_id="a", key="k", content="c", relevance_score=1.0)
        with pytest.raises(ValidationError):
            AgentMemory(agent_id="a", key="k", content="c", relevance_score=-0.1)
        with pytest.raises(ValidationError):
            AgentMemory(agent_id="a", key="k", content="c", relevance_score=1.1)

    def test_is_expired_no_expiry(self) -> None:
        memory = AgentMemory(agent_id="a", key="k", content="c")
        assert memory.is_expired is False

    def test_is_expired_future(self) -> None:
        memory = AgentMemory(
            agent_id="a",
            key="k",
            content="c",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
        assert memory.is_expired is False

    def test_is_expired_past(self) -> None:
        memory = AgentMemory(
            agent_id="a",
            key="k",
            content="c",
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
        assert memory.is_expired is True

    def test_all_memory_types(self) -> None:
        for mt in MemoryType:
            memory = AgentMemory(agent_id="a", key="k", content="c", memory_type=mt)
            assert memory.memory_type == mt

    def test_episodic_memory(self) -> None:
        memory = AgentMemory(
            agent_id="agent-1",
            key="exec_20240101",
            content="User asked about quantum computing. I provided a detailed explanation.",
            memory_type=MemoryType.EPISODIC,
            metadata={"execution_id": "exec-123", "outcome": "success"},
        )
        assert memory.memory_type == MemoryType.EPISODIC
        assert memory.metadata["outcome"] == "success"

    def test_json_roundtrip(self) -> None:
        memory = AgentMemory(
            agent_id="agent-1",
            key="test",
            content="test content",
            memory_type=MemoryType.LONG_TERM,
            embedding=[0.1, 0.2, 0.3],
        )
        data = memory.model_dump()
        restored = AgentMemory.model_validate(data)
        assert restored.id == memory.id
        assert restored.embedding == [0.1, 0.2, 0.3]
        assert restored.memory_type == MemoryType.LONG_TERM

    def test_unique_ids(self) -> None:
        m1 = AgentMemory(agent_id="a", key="k1", content="c")
        m2 = AgentMemory(agent_id="a", key="k2", content="c")
        assert m1.id != m2.id
