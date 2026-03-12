"""Tests unitaires pour ai_engine.models.conversation."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_engine import Conversation, ConversationStatus


class TestConversation:
    def test_creation_minimal(self) -> None:
        conv = Conversation(agent_id="agent-1")
        assert conv.agent_id == "agent-1"
        assert conv.title == ""
        assert conv.status == ConversationStatus.ACTIVE
        assert conv.owner_id is None
        assert conv.message_count == 0
        assert conv.total_tokens == 0
        assert conv.last_message_at is None
        assert conv.summary == ""
        assert conv.metadata == {}

    def test_creation_full(self) -> None:
        conv = Conversation(
            title="Quantum Research",
            agent_id="agent-1",
            owner_id="user-123",
            status=ConversationStatus.ARCHIVED,
            summary="Discussion about quantum computing basics.",
            metadata={"source": "web"},
            message_count=15,
            total_tokens=5000,
        )
        assert conv.title == "Quantum Research"
        assert conv.owner_id == "user-123"
        assert conv.status == ConversationStatus.ARCHIVED
        assert conv.message_count == 15
        assert conv.total_tokens == 5000

    def test_required_agent_id(self) -> None:
        with pytest.raises(ValidationError):
            Conversation(title="No Agent")  # type: ignore[call-arg]

    def test_message_count_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Conversation(agent_id="a", message_count=-1)

    def test_total_tokens_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            Conversation(agent_id="a", total_tokens=-1)

    def test_all_statuses(self) -> None:
        for status in ConversationStatus:
            conv = Conversation(agent_id="a", status=status)
            assert conv.status == status

    def test_json_roundtrip(self) -> None:
        conv = Conversation(
            title="Test",
            agent_id="agent-1",
            owner_id="user-1",
            message_count=5,
        )
        data = conv.model_dump()
        restored = Conversation.model_validate(data)
        assert restored.id == conv.id
        assert restored.title == "Test"
        assert restored.message_count == 5

    def test_unique_ids(self) -> None:
        c1 = Conversation(agent_id="a")
        c2 = Conversation(agent_id="a")
        assert c1.id != c2.id

    def test_timestamps_utc(self) -> None:
        conv = Conversation(agent_id="a")
        assert conv.created_at.tzinfo is not None
        assert conv.updated_at.tzinfo is not None
