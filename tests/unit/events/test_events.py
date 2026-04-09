"""
Tests pour le système d'événements — EventBus + Event definitions.

Couvre :
  - BaseEvent et tous les types d'événements
  - EventBus : subscribe, emit, aemit, unsubscribe, middleware
  - get_event_bus / reset_event_bus
  - Isolation des erreurs de handlers
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from ai_engine.events import (
    AgentCreatedEvent,
    BaseEvent,
    CustomEvent,
    EventBus,
    LLMRequestCompletedEvent,
    MessageReceivedEvent,
    SkillCompletedEvent,
    SkillFailedEvent,
    SkillStartedEvent,
    ToolCalledEvent,
    ToolFailedEvent,
    ToolSucceededEvent,
    get_event_bus,
    reset_event_bus,
)
from ai_engine.exceptions import EventHandlerError
from ai_engine.types import EventType


# ══════════════════════════════════════════════
# Event model tests
# ══════════════════════════════════════════════


class TestEventModels:
    """Tests pour les modèles d'événements Pydantic."""

    def test_base_event_defaults(self) -> None:
        event = CustomEvent(name="test")
        assert event.id
        assert event.timestamp is not None
        assert event.agent_id is None
        assert event.conversation_id is None
        assert event.metadata == {}
        assert event.event_type == EventType.CUSTOM

    def test_base_event_is_frozen(self) -> None:
        event = CustomEvent(name="test")
        with pytest.raises(Exception):
            event.name = "changed"  # type: ignore[misc]

    def test_agent_created_event(self) -> None:
        event = AgentCreatedEvent(agent_id="a1", agent_name="Bot", agent_role="assistant")
        assert event.event_type == EventType.AGENT_CREATED
        assert event.agent_id == "a1"
        assert event.agent_name == "Bot"

    def test_tool_called_event(self) -> None:
        event = ToolCalledEvent(
            tool_name="calculator",
            tool_call_id="tc-1",
            arguments={"expression": "2+2"},
            conversation_id="conv-1",
        )
        assert event.event_type == EventType.TOOL_CALLED
        assert event.arguments["expression"] == "2+2"

    def test_tool_succeeded_event(self) -> None:
        event = ToolSucceededEvent(
            tool_name="calculator",
            tool_call_id="tc-1",
            output_preview="4",
            duration_ms=5.2,
        )
        assert event.duration_ms == 5.2

    def test_tool_failed_event(self) -> None:
        event = ToolFailedEvent(
            tool_name="web_search",
            tool_call_id="tc-2",
            error="Connection timeout",
        )
        assert event.error == "Connection timeout"

    def test_llm_request_completed_event(self) -> None:
        event = LLMRequestCompletedEvent(
            provider_type="openai",
            model="gpt-4o",
            prompt_tokens=100,
            completion_tokens=50,
            duration_ms=432.1,
        )
        assert event.prompt_tokens == 100
        assert event.completion_tokens == 50

    def test_skill_events(self) -> None:
        started = SkillStartedEvent(skill_key="summarize", skill_name="Summarize")
        completed = SkillCompletedEvent(skill_key="summarize", duration_ms=200.0)
        failed = SkillFailedEvent(skill_key="summarize", error="LLM error")

        assert started.event_type == EventType.SKILL_STARTED
        assert completed.event_type == EventType.SKILL_COMPLETED
        assert failed.event_type == EventType.SKILL_FAILED

    def test_custom_event(self) -> None:
        event = CustomEvent(name="my_event", data={"foo": "bar"})
        assert event.name == "my_event"
        assert event.data["foo"] == "bar"

    def test_message_received_event(self) -> None:
        event = MessageReceivedEvent(
            message_id="msg-1",
            model="gpt-4o",
            content_preview="Hello",
            agent_id="agent-1",
        )
        assert event.model == "gpt-4o"


# ══════════════════════════════════════════════
# EventBus tests
# ══════════════════════════════════════════════


class TestEventBus:
    """Tests pour EventBus."""

    @pytest.fixture
    def bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def tool_event(self) -> ToolSucceededEvent:
        return ToolSucceededEvent(tool_name="calc", tool_call_id="tc-1")

    def test_subscribe_and_emit(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        received: list[BaseEvent] = []
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: received.append(e))
        bus.emit(tool_event)
        assert len(received) == 1
        assert received[0] is tool_event

    def test_on_decorator(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        received: list[BaseEvent] = []

        @bus.on(EventType.TOOL_SUCCEEDED)
        def handler(event: BaseEvent) -> None:
            received.append(event)

        bus.emit(tool_event)
        assert len(received) == 1

    def test_multiple_handlers(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        calls: list[str] = []
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: calls.append("h1"))
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: calls.append("h2"))
        bus.emit(tool_event)
        assert calls == ["h1", "h2"]

    def test_no_handler_no_error(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        # Émettre sans aucun handler ne doit pas lever d'exception
        bus.emit(tool_event)

    def test_wrong_event_type_not_called(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        called = MagicMock()
        bus.subscribe(EventType.TOOL_FAILED, called)
        bus.emit(tool_event)
        called.assert_not_called()

    def test_wildcard_subscriber(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        received: list[BaseEvent] = []
        bus.subscribe_all(lambda e: received.append(e))
        bus.emit(tool_event)
        other = ToolFailedEvent(tool_name="x", tool_call_id="tc-2", error="err")
        bus.emit(other)
        assert len(received) == 2

    def test_unsubscribe(self, bus: EventBus, tool_event: ToolSucceededEvent) -> None:
        calls: list[int] = []
        handler = lambda e: calls.append(1)  # noqa: E731
        bus.subscribe(EventType.TOOL_SUCCEEDED, handler)
        bus.emit(tool_event)
        bus.unsubscribe(EventType.TOOL_SUCCEEDED, handler)
        bus.emit(tool_event)
        assert len(calls) == 1

    def test_unsubscribe_nonexistent_returns_false(self, bus: EventBus) -> None:
        result = bus.unsubscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        assert result is False

    def test_handler_error_is_isolated(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        """Un handler qui crash ne doit pas bloquer les autres."""
        results: list[str] = []

        def bad_handler(e: BaseEvent) -> None:
            raise RuntimeError("boom")

        def good_handler(e: BaseEvent) -> None:
            results.append("ok")

        bus.subscribe(EventType.TOOL_SUCCEEDED, bad_handler)
        bus.subscribe(EventType.TOOL_SUCCEEDED, good_handler)
        # Ne doit pas lever d'exception
        bus.emit(tool_event)
        assert results == ["ok"]

    def test_raise_on_handler_error(
        self, tool_event: ToolSucceededEvent
    ) -> None:
        bus = EventBus(raise_on_handler_error=True)

        def bad(e: BaseEvent) -> None:
            raise RuntimeError("fail")

        bus.subscribe(EventType.TOOL_SUCCEEDED, bad)
        with pytest.raises(EventHandlerError):
            bus.emit(tool_event)

    def test_middleware_called(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        middleware_received: list[BaseEvent] = []
        bus.add_middleware(lambda e: middleware_received.append(e))
        bus.emit(tool_event)
        assert len(middleware_received) == 1
        assert middleware_received[0] is tool_event

    def test_handler_count(self, bus: EventBus) -> None:
        assert bus.handler_count() == 0
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        bus.subscribe(EventType.TOOL_FAILED, lambda e: None)
        assert bus.handler_count() == 3
        assert bus.handler_count(EventType.TOOL_SUCCEEDED) == 2
        assert bus.handler_count(EventType.TOOL_FAILED) == 1

    def test_clear_specific_event(self, bus: EventBus) -> None:
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        bus.subscribe(EventType.TOOL_FAILED, lambda e: None)
        bus.clear(EventType.TOOL_SUCCEEDED)
        assert bus.handler_count(EventType.TOOL_SUCCEEDED) == 0
        assert bus.handler_count(EventType.TOOL_FAILED) == 1

    def test_clear_all(self, bus: EventBus) -> None:
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        bus.subscribe(EventType.TOOL_FAILED, lambda e: None)
        bus.clear()
        assert bus.handler_count() == 0

    def test_repr(self, bus: EventBus) -> None:
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: None)
        assert "handlers=1" in repr(bus)

    # ── Async ─────────────────────────────────────────────────────────────────

    async def test_aemit_async_handler(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        received: list[BaseEvent] = []

        async def async_handler(event: BaseEvent) -> None:
            received.append(event)

        bus.subscribe(EventType.TOOL_SUCCEEDED, async_handler)
        await bus.aemit(tool_event)
        assert len(received) == 1

    async def test_aemit_sync_handler(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        received: list[BaseEvent] = []
        bus.subscribe(EventType.TOOL_SUCCEEDED, lambda e: received.append(e))
        await bus.aemit(tool_event)
        assert len(received) == 1

    async def test_aemit_mixed_handlers(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        calls: list[str] = []

        def sync_h(e: BaseEvent) -> None:
            calls.append("sync")

        async def async_h(e: BaseEvent) -> None:
            calls.append("async")

        bus.subscribe(EventType.TOOL_SUCCEEDED, sync_h)
        bus.subscribe(EventType.TOOL_SUCCEEDED, async_h)
        await bus.aemit(tool_event)
        assert "sync" in calls
        assert "async" in calls

    async def test_aemit_error_isolated(
        self, bus: EventBus, tool_event: ToolSucceededEvent
    ) -> None:
        results: list[str] = []

        async def bad(e: BaseEvent) -> None:
            raise ValueError("async boom")

        async def good(e: BaseEvent) -> None:
            results.append("ok")

        bus.subscribe(EventType.TOOL_SUCCEEDED, bad)
        bus.subscribe(EventType.TOOL_SUCCEEDED, good)
        await bus.aemit(tool_event)
        assert results == ["ok"]


# ══════════════════════════════════════════════
# Global bus tests
# ══════════════════════════════════════════════


class TestGlobalEventBus:
    """Tests pour get_event_bus / reset_event_bus."""

    def setup_method(self) -> None:
        reset_event_bus()

    def teardown_method(self) -> None:
        reset_event_bus()

    def test_get_event_bus_singleton(self) -> None:
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_creates_new_instance(self) -> None:
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2

    def test_global_bus_works(self) -> None:
        bus = get_event_bus()
        received: list[BaseEvent] = []
        bus.subscribe(EventType.CUSTOM, lambda e: received.append(e))
        bus.emit(CustomEvent(name="test"))
        assert len(received) == 1
