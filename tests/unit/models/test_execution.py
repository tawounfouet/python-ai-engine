"""Tests unitaires pour ai_engine.models.execution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ai_engine import Execution, ExecutionStatus, ExecutionStep, StepType, TokenUsage


class TestExecutionStep:
    def test_creation_minimal(self) -> None:
        step = ExecutionStep(
            execution_id="exec-1",
            step_type=StepType.LLM_CALL,
        )
        assert step.execution_id == "exec-1"
        assert step.step_type == StepType.LLM_CALL
        assert step.order == 0
        assert step.input_data == {}
        assert step.output_data == {}
        assert step.error == ""
        assert step.tool_id is None
        assert step.tokens_used == 0
        assert step.cost == 0.0
        assert step.duration_ms == 0

    def test_creation_full(self) -> None:
        now = datetime.now(UTC)
        step = ExecutionStep(
            execution_id="exec-1",
            step_type=StepType.TOOL_CALL,
            order=3,
            input_data={"tool": "web_search", "args": {"query": "test"}},
            output_data={"result": "Found 10 results"},
            tool_id="tool-ws",
            tokens_used=150,
            cost=0.002,
            duration_ms=340,
            started_at=now,
            completed_at=now + timedelta(milliseconds=340),
        )
        assert step.step_type == StepType.TOOL_CALL
        assert step.order == 3
        assert step.tool_id == "tool-ws"
        assert step.tokens_used == 150
        assert step.duration_ms == 340

    def test_error_step(self) -> None:
        step = ExecutionStep(
            execution_id="exec-1",
            step_type=StepType.ERROR,
            error="ConnectionError: API timeout",
        )
        assert step.step_type == StepType.ERROR
        assert "timeout" in step.error

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionStep(step_type=StepType.LLM_CALL)  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            ExecutionStep(execution_id="e")  # type: ignore[call-arg]

    def test_non_negative_metrics(self) -> None:
        with pytest.raises(ValidationError):
            ExecutionStep(execution_id="e", step_type=StepType.LLM_CALL, tokens_used=-1)
        with pytest.raises(ValidationError):
            ExecutionStep(execution_id="e", step_type=StepType.LLM_CALL, cost=-0.01)
        with pytest.raises(ValidationError):
            ExecutionStep(execution_id="e", step_type=StepType.LLM_CALL, duration_ms=-1)

    def test_all_step_types(self) -> None:
        for st in StepType:
            step = ExecutionStep(execution_id="e", step_type=st)
            assert step.step_type == st

    def test_json_roundtrip(self) -> None:
        step = ExecutionStep(
            execution_id="exec-1",
            step_type=StepType.TOOL_RESULT,
            order=2,
            output_data={"result": "ok"},
        )
        data = step.model_dump()
        restored = ExecutionStep.model_validate(data)
        assert restored.id == step.id
        assert restored.step_type == StepType.TOOL_RESULT


class TestExecution:
    def test_creation_minimal(self) -> None:
        execution = Execution(agent_id="agent-1")
        assert execution.agent_id == "agent-1"
        assert execution.status == ExecutionStatus.PENDING
        assert execution.graph_id is None
        assert execution.conversation_id is None
        assert execution.input_data == {}
        assert execution.output_data == {}
        assert execution.error == ""
        assert execution.total_steps == 0
        assert execution.started_at is None
        assert execution.completed_at is None
        assert execution.token_usage.total_tokens == 0

    def test_creation_full(self) -> None:
        now = datetime.now(UTC)
        execution = Execution(
            agent_id="agent-1",
            graph_id="graph-1",
            conversation_id="conv-1",
            status=ExecutionStatus.SUCCESS,
            input_data={"prompt": "Analyze this"},
            output_data={"result": "Analysis complete"},
            token_usage=TokenUsage(
                prompt_tokens=100,
                completion_tokens=500,
                total_tokens=600,
                estimated_cost_usd=0.01,
            ),
            total_steps=5,
            started_at=now - timedelta(seconds=10),
            completed_at=now,
            metadata={"source": "api", "user_id": "u-123"},
        )
        assert execution.status == ExecutionStatus.SUCCESS
        assert execution.token_usage.total_tokens == 600
        assert execution.total_steps == 5

    def test_required_agent_id(self) -> None:
        with pytest.raises(ValidationError):
            Execution(status=ExecutionStatus.PENDING)  # type: ignore[call-arg]

    def test_duration(self) -> None:
        now = datetime.now(UTC)
        execution = Execution(
            agent_id="a",
            started_at=now - timedelta(seconds=5),
            completed_at=now,
        )
        assert execution.duration is not None
        assert abs(execution.duration.total_seconds() - 5.0) < 0.01

    def test_duration_ms(self) -> None:
        now = datetime.now(UTC)
        execution = Execution(
            agent_id="a",
            started_at=now - timedelta(milliseconds=1500),
            completed_at=now,
        )
        assert execution.duration_ms is not None
        assert abs(execution.duration_ms - 1500) < 10

    def test_duration_none_when_not_completed(self) -> None:
        execution = Execution(agent_id="a")
        assert execution.duration is None
        assert execution.duration_ms is None

    def test_is_terminal(self) -> None:
        for status in [
            ExecutionStatus.SUCCESS,
            ExecutionStatus.FAILED,
            ExecutionStatus.CANCELLED,
        ]:
            execution = Execution(agent_id="a", status=status)
            assert execution.is_terminal is True

        for status in [ExecutionStatus.PENDING, ExecutionStatus.RUNNING]:
            execution = Execution(agent_id="a", status=status)
            assert execution.is_terminal is False

    def test_all_statuses(self) -> None:
        for status in ExecutionStatus:
            execution = Execution(agent_id="a", status=status)
            assert execution.status == status

    def test_json_roundtrip(self) -> None:
        execution = Execution(
            agent_id="agent-1",
            status=ExecutionStatus.RUNNING,
            input_data={"prompt": "test"},
            total_steps=3,
        )
        data = execution.model_dump()
        restored = Execution.model_validate(data)
        assert restored.id == execution.id
        assert restored.status == ExecutionStatus.RUNNING
        assert restored.total_steps == 3

    def test_token_usage_default(self) -> None:
        execution = Execution(agent_id="a")
        assert execution.token_usage.prompt_tokens == 0
        assert execution.token_usage.completion_tokens == 0
        assert execution.token_usage.total_tokens == 0
        assert execution.token_usage.estimated_cost_usd == 0.0
