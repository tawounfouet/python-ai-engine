"""Tests unitaires pour ai_engine.models.message."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_engine import Message, MessageRole, TokenUsage, ToolCall, ToolResult


class TestToolCall:
    def test_creation(self) -> None:
        tc = ToolCall(name="web_search", arguments={"query": "test"})
        assert tc.name == "web_search"
        assert tc.arguments == {"query": "test"}
        assert tc.id  # auto-generated

    def test_empty_arguments(self) -> None:
        tc = ToolCall(name="noop")
        assert tc.arguments == {}

    def test_json_roundtrip(self) -> None:
        tc = ToolCall(name="calc", arguments={"expr": "2+2"})
        data = tc.model_dump()
        restored = ToolCall.model_validate(data)
        assert restored.name == tc.name
        assert restored.arguments == tc.arguments


class TestToolResult:
    def test_creation(self) -> None:
        tr = ToolResult(tool_call_id="call-123", output="Result: 4")
        assert tr.tool_call_id == "call-123"
        assert tr.output == "Result: 4"
        assert tr.is_error is False

    def test_error_result(self) -> None:
        tr = ToolResult(
            tool_call_id="call-123",
            output="ConnectionError: timeout",
            is_error=True,
        )
        assert tr.is_error is True

    def test_required_tool_call_id(self) -> None:
        with pytest.raises(ValidationError):
            ToolResult(output="result")  # type: ignore[call-arg]


class TestTokenUsage:
    def test_defaults(self) -> None:
        tu = TokenUsage()
        assert tu.prompt_tokens == 0
        assert tu.completion_tokens == 0
        assert tu.total_tokens == 0
        assert tu.estimated_cost_usd == 0.0

    def test_custom_values(self) -> None:
        tu = TokenUsage(
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            estimated_cost_usd=0.005,
        )
        assert tu.prompt_tokens == 100
        assert tu.total_tokens == 300

    def test_non_negative(self) -> None:
        with pytest.raises(ValidationError):
            TokenUsage(prompt_tokens=-1)
        with pytest.raises(ValidationError):
            TokenUsage(estimated_cost_usd=-0.01)

    def test_from_total(self) -> None:
        tu = TokenUsage.from_total(500, cost=0.01)
        assert tu.total_tokens == 500
        assert tu.estimated_cost_usd == 0.01
        assert tu.prompt_tokens == 0
        assert tu.completion_tokens == 0

    def test_json_roundtrip(self) -> None:
        tu = TokenUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30)
        data = tu.model_dump()
        restored = TokenUsage.model_validate(data)
        assert restored == tu


class TestMessage:
    def test_creation_user_message(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.USER,
            content="Hello!",
        )
        assert msg.conversation_id == "conv-1"
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.tool_calls == []
        assert msg.tool_result is None
        assert msg.token_usage is None
        assert msg.metadata == {}

    def test_creation_assistant_with_tool_calls(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.ASSISTANT,
            content="",
            tool_calls=[
                ToolCall(name="web_search", arguments={"query": "python"}),
                ToolCall(name="calculator", arguments={"expr": "2+2"}),
            ],
        )
        assert msg.role == MessageRole.ASSISTANT
        assert len(msg.tool_calls) == 2
        assert msg.tool_calls[0].name == "web_search"
        assert msg.tool_calls[1].name == "calculator"

    def test_creation_tool_result(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.TOOL,
            content="Search results...",
            tool_result=ToolResult(
                tool_call_id="call-abc",
                output="Search results...",
            ),
        )
        assert msg.role == MessageRole.TOOL
        assert msg.tool_result is not None
        assert msg.tool_result.tool_call_id == "call-abc"

    def test_creation_with_token_usage(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.ASSISTANT,
            content="Response",
            token_usage=TokenUsage(
                prompt_tokens=50,
                completion_tokens=100,
                total_tokens=150,
            ),
        )
        assert msg.token_usage is not None
        assert msg.token_usage.total_tokens == 150

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Message(role=MessageRole.USER, content="No conv")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            Message(conversation_id="c", content="No role")  # type: ignore[call-arg]

    def test_all_roles(self) -> None:
        for role in MessageRole:
            msg = Message(conversation_id="c", role=role)
            assert msg.role == role

    def test_json_serialization(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.ASSISTANT,
            content="Hello",
            tool_calls=[ToolCall(name="test", arguments={"a": 1})],
        )
        json_str = msg.model_dump_json()
        data = json.loads(json_str)
        assert data["role"] == "assistant"
        assert len(data["tool_calls"]) == 1
        assert data["tool_calls"][0]["name"] == "test"

    def test_model_dump_roundtrip(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.USER,
            content="Test",
            metadata={"source": "api"},
        )
        data = msg.model_dump()
        restored = Message.model_validate(data)
        assert restored.id == msg.id
        assert restored.content == "Test"
        assert restored.metadata["source"] == "api"

    def test_system_message(self) -> None:
        msg = Message(
            conversation_id="conv-1",
            role=MessageRole.SYSTEM,
            content="You are a helpful assistant.",
        )
        assert msg.role == MessageRole.SYSTEM
