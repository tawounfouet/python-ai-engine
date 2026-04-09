"""
AI Engine — Event System.

Bus d'événements et définitions pour le découplage interne des composants.
Remplace les Django signals dans le contexte standalone.

Usage:
    from ai_engine.events import EventBus, EventType, get_event_bus
    from ai_engine.events import ToolCalledEvent, ToolSucceededEvent

    bus = get_event_bus()

    @bus.on(EventType.TOOL_SUCCEEDED)
    def on_tool_success(event: ToolSucceededEvent) -> None:
        print(f"✅ {event.tool_name} succeeded in {event.duration_ms}ms")

    bus.emit(ToolSucceededEvent(
        tool_name="calculator",
        tool_call_id="tc-1",
        duration_ms=12.5,
    ))
"""

from __future__ import annotations

__all__ = [
    # Bus
    "EventBus",
    "get_event_bus",
    "reset_event_bus",
    # Base event
    "BaseEvent",
    # Agent events
    "AgentCreatedEvent",
    "AgentUpdatedEvent",
    "AgentDeletedEvent",
    # Conversation events
    "ConversationStartedEvent",
    "ConversationEndedEvent",
    # Message events
    "MessageSentEvent",
    "MessageReceivedEvent",
    # Tool events
    "ToolCalledEvent",
    "ToolSucceededEvent",
    "ToolFailedEvent",
    # LLM events
    "LLMRequestStartedEvent",
    "LLMRequestCompletedEvent",
    "LLMRequestFailedEvent",
    # Skill events
    "SkillStartedEvent",
    "SkillCompletedEvent",
    "SkillFailedEvent",
    # Execution events
    "ExecutionStartedEvent",
    "ExecutionCompletedEvent",
    "ExecutionFailedEvent",
    # Custom
    "CustomEvent",
]

from ai_engine.events.bus import EventBus, get_event_bus, reset_event_bus
from ai_engine.events.events import (
    AgentCreatedEvent,
    AgentDeletedEvent,
    AgentUpdatedEvent,
    BaseEvent,
    ConversationEndedEvent,
    ConversationStartedEvent,
    CustomEvent,
    ExecutionCompletedEvent,
    ExecutionFailedEvent,
    ExecutionStartedEvent,
    LLMRequestCompletedEvent,
    LLMRequestFailedEvent,
    LLMRequestStartedEvent,
    MessageReceivedEvent,
    MessageSentEvent,
    SkillCompletedEvent,
    SkillFailedEvent,
    SkillStartedEvent,
    ToolCalledEvent,
    ToolFailedEvent,
    ToolSucceededEvent,
)
