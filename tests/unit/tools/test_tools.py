"""
Tests pour le Tool System (Registry + Executor).

Tests unitaires pour :
- ToolRegistry : enregistrement, résolution, lookup
- ToolExecutor : exécution unitaire, boucle tool-calling
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from ai_engine.exceptions import ToolExecutionError, ToolNotFoundError
from ai_engine.models.message import Message, ToolCall, ToolResult
from ai_engine.models.tool import ToolDefinition
from ai_engine.services.llm.base import LLMResponse
from ai_engine.services.llm.base import ToolCall as LLMToolCall
from ai_engine.tools.executor import ToolExecutor
from ai_engine.tools.registry import ToolRegistry
from ai_engine.types import MessageRole, ToolType


# ──────────────────────────────────────────────
# Fixtures & helpers
# ──────────────────────────────────────────────


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry()


@pytest.fixture
def tool_definition() -> ToolDefinition:
    return ToolDefinition(
        key="calculator",
        name="Calculator",
        description="Performs basic math operations",
        tool_type=ToolType.FUNCTION,
        parameters_schema={
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Math expression"},
            },
            "required": ["expression"],
        },
    )


def _add(a: int, b: int) -> int:
    return a + b


def _add_str(a: str, b: str) -> str:
    return a + b


def _greet(name: str) -> dict[str, str]:
    return {"greeting": f"Hello, {name}!"}


def _failing(**kwargs: object) -> str:
    raise RuntimeError("Tool crashed!")


async def _async_add(a: int, b: int) -> int:
    return a + b


# ══════════════════════════════════════════════
# ToolRegistry Tests
# ══════════════════════════════════════════════


class TestToolRegistry:
    """Tests pour ToolRegistry."""

    def test_register_and_get(self, registry: ToolRegistry) -> None:
        registry.register("add", _add)
        fn = registry.get("add")
        assert fn is _add
        assert registry.has("add")
        assert "add" in registry

    def test_get_not_found(self, registry: ToolRegistry) -> None:
        with pytest.raises(ToolNotFoundError):
            registry.get("nonexistent")

    def test_register_with_definition(
        self, registry: ToolRegistry, tool_definition: ToolDefinition
    ) -> None:
        registry.register("calculator", _add, definition=tool_definition)
        assert registry.has("calculator")
        assert registry.get_definition("calculator") is tool_definition

    def test_register_tool(
        self, registry: ToolRegistry, tool_definition: ToolDefinition
    ) -> None:
        registry.register_tool(tool_definition, _add)
        assert registry.has("calculator")
        assert registry.get("calculator") is _add

    def test_register_non_callable_raises(self, registry: ToolRegistry) -> None:
        with pytest.raises(TypeError, match="must be callable"):
            registry.register("bad", "not a function")  # type: ignore[arg-type]

    def test_keys(self, registry: ToolRegistry) -> None:
        registry.register("a", _add)
        registry.register("b", _greet)
        assert sorted(registry.keys()) == ["a", "b"]

    def test_len(self, registry: ToolRegistry) -> None:
        assert len(registry) == 0
        registry.register("a", _add)
        assert len(registry) == 1

    def test_clear(self, registry: ToolRegistry) -> None:
        registry.register("a", _add)
        registry.register("b", _greet)
        registry.clear()
        assert len(registry) == 0
        assert not registry.has("a")

    def test_has_returns_false_for_missing(self, registry: ToolRegistry) -> None:
        assert not registry.has("missing")
        assert "missing" not in registry

    def test_get_definition_returns_none_without_definition(self, registry: ToolRegistry) -> None:
        registry.register("add", _add)
        assert registry.get_definition("add") is None

    def test_resolve_from_path(self, registry: ToolRegistry) -> None:
        registry.resolve_from_path("json_dumps", "json.dumps")
        fn = registry.get("json_dumps")
        assert callable(fn)
        assert fn({"a": 1}) == '{"a": 1}'

    def test_resolve_from_path_empty(self, registry: ToolRegistry) -> None:
        with pytest.raises(ValueError, match="Empty function_path"):
            registry.resolve_from_path("bad", "")

    def test_resolve_from_path_invalid(self, registry: ToolRegistry) -> None:
        with pytest.raises(ValueError, match="Invalid function_path"):
            registry.resolve_from_path("bad", "no_dot_in_path")

    def test_resolve_from_path_module_not_found(self, registry: ToolRegistry) -> None:
        with pytest.raises(ImportError):
            registry.resolve_from_path("bad", "nonexistent_module.func")


# ══════════════════════════════════════════════
# ToolExecutor — Exécution unitaire
# ══════════════════════════════════════════════


class TestToolExecutor:
    """Tests pour ToolExecutor.execute_call."""

    @pytest.fixture
    def executor(self, registry: ToolRegistry) -> ToolExecutor:
        registry.register("add_str", _add_str)
        registry.register("greet", _greet)
        registry.register("failing", _failing)
        return ToolExecutor(registry)

    def test_execute_call_success_string(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="c1", name="add_str", arguments={"a": "x", "b": "y"})
        result = executor.execute_call(tc)
        assert result.tool_call_id == "c1"
        assert result.output == "xy"
        assert result.is_error is False

    def test_execute_call_success_dict(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="c2", name="greet", arguments={"name": "Alice"})
        result = executor.execute_call(tc)
        assert result.tool_call_id == "c2"
        assert '"Hello, Alice!"' in result.output
        assert result.is_error is False

    def test_execute_call_tool_not_found(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="c3", name="nonexistent", arguments={})
        result = executor.execute_call(tc)
        assert result.tool_call_id == "c3"
        assert result.is_error is True
        assert "not found" in result.output

    def test_execute_call_tool_raises(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="c4", name="failing", arguments={})
        result = executor.execute_call(tc)
        assert result.tool_call_id == "c4"
        assert result.is_error is True
        assert "Tool crashed!" in result.output


# ══════════════════════════════════════════════
# ToolExecutor — Async
# ══════════════════════════════════════════════


class TestToolExecutorAsync:
    """Tests async pour ToolExecutor."""

    @pytest.fixture
    def executor(self) -> ToolExecutor:
        registry = ToolRegistry()
        registry.register("add_str", _add_str)
        registry.register("async_add", _async_add)
        registry.register("failing", _failing)
        return ToolExecutor(registry)

    @pytest.mark.asyncio
    async def test_aexecute_call_sync_func(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="ac1", name="add_str", arguments={"a": "x", "b": "y"})
        result = await executor.aexecute_call(tc)
        assert result.output == "xy"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_aexecute_call_async_func(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="ac2", name="async_add", arguments={"a": 7, "b": 8})
        result = await executor.aexecute_call(tc)
        assert result.output == "15"
        assert result.is_error is False

    @pytest.mark.asyncio
    async def test_aexecute_call_not_found(self, executor: ToolExecutor) -> None:
        tc = ToolCall(id="ac3", name="nope", arguments={})
        result = await executor.aexecute_call(tc)
        assert result.is_error is True


# ══════════════════════════════════════════════
# ToolExecutor — Boucle tool-calling
# ══════════════════════════════════════════════


class TestToolLoop:
    """Tests pour run_tool_loop."""

    @pytest.fixture
    def registry_with_defs(self, tool_definition: ToolDefinition) -> ToolRegistry:
        registry = ToolRegistry()
        registry.register_tool(tool_definition, _add_str)
        return registry

    @pytest.fixture
    def executor(self, registry_with_defs: ToolRegistry) -> ToolExecutor:
        return ToolExecutor(registry_with_defs)

    @staticmethod
    def _make_response(
        content: str = "",
        tool_calls: list[LLMToolCall] | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content=content,
            model="test-model",
            tool_calls=tool_calls or [],
        )

    def test_no_tool_calls_returns_immediately(self, executor: ToolExecutor) -> None:
        mock_client = Mock()
        mock_client.complete.return_value = self._make_response(content="Hello!")

        messages = [
            Message(conversation_id="c1", role=MessageRole.USER, content="Hi"),
        ]

        response = executor.run_tool_loop(
            client=mock_client, messages=messages, conversation_id="c1",
        )

        assert response.content == "Hello!"
        mock_client.complete.assert_called_once()

    def test_single_tool_call_then_response(self, executor: ToolExecutor) -> None:
        mock_client = Mock()
        mock_client.complete.side_effect = [
            self._make_response(
                tool_calls=[
                    LLMToolCall(id="tc1", function_name="calculator", arguments={"a": "x", "b": "y"}),
                ],
            ),
            self._make_response(content="The answer is xy."),
        ]

        messages = [
            Message(conversation_id="c1", role=MessageRole.USER, content="Concatenate x and y"),
        ]

        response = executor.run_tool_loop(
            client=mock_client, messages=messages, conversation_id="c1",
        )

        assert response.content == "The answer is xy."
        assert mock_client.complete.call_count == 2

    def test_max_iterations_reached(self, executor: ToolExecutor) -> None:
        mock_client = Mock()
        mock_client.complete.return_value = self._make_response(
            tool_calls=[
                LLMToolCall(id="loop", function_name="calculator", arguments={"a": "1", "b": "1"}),
            ],
        )

        messages = [
            Message(conversation_id="c1", role=MessageRole.USER, content="Loop"),
        ]

        with pytest.raises(ToolExecutionError, match="Max iterations"):
            executor.run_tool_loop(
                client=mock_client, messages=messages, max_iterations=3, conversation_id="c1",
            )

        assert mock_client.complete.call_count == 3

    def test_get_tools_schema_with_definition(self, executor: ToolExecutor) -> None:
        schemas = executor._get_tools_schema()
        assert len(schemas) == 1
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "calculator"

    def test_get_tools_schema_without_definition(self) -> None:
        registry = ToolRegistry()
        registry.register("simple", _add)
        executor = ToolExecutor(registry)

        schemas = executor._get_tools_schema()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "simple"
