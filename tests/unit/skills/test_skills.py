"""
Tests pour le Skills System — BaseSkill + SkillRegistry.

Couvre :
  - BaseSkill : définition, définition du modèle, exécution avec events
  - SkillRegistry : register, get, list, validation des tools, EventBus
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from ai_engine.events import (
    EventBus,
    SkillCompletedEvent,
    SkillFailedEvent,
    SkillStartedEvent,
)
from ai_engine.exceptions import SkillExecutionError, SkillNotFoundError
from ai_engine.skills import BaseSkill, SkillRegistry
from ai_engine.types import EventType, SkillCategory


# ──────────────────────────────────────────────
# Concrete skill fixtures
# ──────────────────────────────────────────────


class EchoSkill(BaseSkill):
    """Skill de test : retourne simplement le texte fourni."""

    key = "echo"
    name = "Echo Skill"
    description = "Echoes the input text back."
    category = SkillCategory.CUSTOM
    required_tool_keys: list[str] = []

    def run(self, *, llm_client: Any, text: str = "", **kwargs: Any) -> str:
        return f"Echo: {text}"


class MultiToolSkill(BaseSkill):
    """Skill de test nécessitant plusieurs tools."""

    key = "multi_tool"
    name = "Multi-Tool Skill"
    description = "Requires multiple tools."
    category = SkillCategory.RESEARCH
    required_tool_keys = ["web_search", "calculator", "http_get"]

    def run(self, *, llm_client: Any, **kwargs: Any) -> str:
        return "done"


class FailingSkill(BaseSkill):
    """Skill de test qui échoue toujours."""

    key = "failing"
    name = "Failing Skill"
    description = "Always raises."
    category = SkillCategory.CUSTOM
    required_tool_keys: list[str] = []

    def run(self, *, llm_client: Any, **kwargs: Any) -> str:
        raise RuntimeError("Skill crashed!")


# ══════════════════════════════════════════════
# BaseSkill tests
# ══════════════════════════════════════════════


class TestBaseSkill:
    """Tests pour BaseSkill."""

    @pytest.fixture
    def skill(self) -> EchoSkill:
        return EchoSkill()

    @pytest.fixture
    def mock_llm(self) -> MagicMock:
        return MagicMock()

    def test_key_required_on_subclass(self) -> None:
        with pytest.raises(TypeError, match="must define a non-empty 'key'"):

            class BadSkill(BaseSkill):
                key = ""

                def run(self, **kwargs: Any) -> str:
                    return ""  # noqa: E704

    def test_run_returns_result(self, skill: EchoSkill, mock_llm: MagicMock) -> None:
        result = skill.run(llm_client=mock_llm, text="hello")
        assert result == "Echo: hello"

    def test_definition_property(self, skill: EchoSkill) -> None:
        defn = skill.definition
        assert defn.key == "echo"
        assert defn.name == "Echo Skill"
        assert defn.category == SkillCategory.CUSTOM

    def test_repr(self, skill: EchoSkill) -> None:
        assert "echo" in repr(skill)

    def test_execute_emits_started_and_completed(
        self, skill: EchoSkill, mock_llm: MagicMock
    ) -> None:
        bus = EventBus()
        skill.inject_event_bus(bus)

        received: list[Any] = []
        bus.subscribe(EventType.SKILL_STARTED, lambda e: received.append(e))
        bus.subscribe(EventType.SKILL_COMPLETED, lambda e: received.append(e))

        result = skill.execute(llm_client=mock_llm, text="test", agent_id="a1")

        assert result == "Echo: test"
        assert len(received) == 2
        assert isinstance(received[0], SkillStartedEvent)
        assert isinstance(received[1], SkillCompletedEvent)
        assert received[0].skill_key == "echo"
        assert received[1].duration_ms is not None

    def test_execute_emits_failed_on_error(self, mock_llm: MagicMock) -> None:
        skill = FailingSkill()
        bus = EventBus()
        skill.inject_event_bus(bus)

        failed_events: list[Any] = []
        bus.subscribe(EventType.SKILL_FAILED, lambda e: failed_events.append(e))

        with pytest.raises(RuntimeError, match="Skill crashed"):
            skill.execute(llm_client=mock_llm)

        assert len(failed_events) == 1
        assert isinstance(failed_events[0], SkillFailedEvent)
        assert "Skill crashed" in failed_events[0].error

    def test_execute_without_event_bus(
        self, skill: EchoSkill, mock_llm: MagicMock
    ) -> None:
        # Sans EventBus, execute() doit fonctionner normalement
        result = skill.execute(llm_client=mock_llm, text="no bus")
        assert result == "Echo: no bus"

    async def test_arun_delegates_to_run(
        self, skill: EchoSkill, mock_llm: MagicMock
    ) -> None:
        result = await skill.arun(llm_client=mock_llm, text="async")
        assert result == "Echo: async"

    async def test_aexecute_emits_events(
        self, skill: EchoSkill, mock_llm: MagicMock
    ) -> None:
        bus = EventBus()
        skill.inject_event_bus(bus)

        received: list[Any] = []
        bus.subscribe(EventType.SKILL_STARTED, lambda e: received.append(("start", e)))
        bus.subscribe(EventType.SKILL_COMPLETED, lambda e: received.append(("done", e)))

        result = await skill.aexecute(llm_client=mock_llm, text="async exec")

        assert result == "Echo: async exec"
        assert received[0][0] == "start"
        assert received[1][0] == "done"


# ══════════════════════════════════════════════
# SkillRegistry tests
# ══════════════════════════════════════════════


class TestSkillRegistry:
    """Tests pour SkillRegistry."""

    @pytest.fixture
    def registry(self) -> SkillRegistry:
        return SkillRegistry()

    @pytest.fixture
    def echo(self) -> EchoSkill:
        return EchoSkill()

    @pytest.fixture
    def multi(self) -> MultiToolSkill:
        return MultiToolSkill()

    def test_register_and_get(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        registry.register(echo)
        assert registry.has("echo")
        assert registry.get("echo") is echo

    def test_get_not_found(self, registry: SkillRegistry) -> None:
        with pytest.raises(SkillNotFoundError, match="echo"):
            registry.get("echo")

    def test_get_or_none(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        assert registry.get_or_none("echo") is None
        registry.register(echo)
        assert registry.get_or_none("echo") is echo

    def test_register_many(
        self, registry: SkillRegistry, echo: EchoSkill, multi: MultiToolSkill
    ) -> None:
        registry.register_many([echo, multi])
        assert len(registry) == 2

    def test_unregister(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        registry.register(echo)
        result = registry.unregister("echo")
        assert result is True
        assert not registry.has("echo")

    def test_unregister_nonexistent(self, registry: SkillRegistry) -> None:
        result = registry.unregister("nonexistent")
        assert result is False

    def test_keys(
        self, registry: SkillRegistry, echo: EchoSkill, multi: MultiToolSkill
    ) -> None:
        registry.register_many([echo, multi])
        assert set(registry.keys()) == {"echo", "multi_tool"}

    def test_list_all(
        self, registry: SkillRegistry, echo: EchoSkill, multi: MultiToolSkill
    ) -> None:
        registry.register_many([echo, multi])
        skills = registry.list_all()
        assert len(skills) == 2

    def test_list_active(self, registry: SkillRegistry) -> None:
        active = EchoSkill()
        inactive = MultiToolSkill()
        inactive.is_active = False
        registry.register_many([active, inactive])
        assert len(registry.list_active()) == 1

    def test_list_by_category(
        self, registry: SkillRegistry, echo: EchoSkill, multi: MultiToolSkill
    ) -> None:
        registry.register_many([echo, multi])
        research = registry.list_by_category(SkillCategory.RESEARCH)
        custom = registry.list_by_category(SkillCategory.CUSTOM)
        assert len(research) == 1
        assert len(custom) == 1

    def test_get_definitions(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        registry.register(echo)
        defs = registry.get_definitions()
        assert len(defs) == 1
        assert defs[0].key == "echo"

    def test_get_missing_tools_none_missing(
        self, registry: SkillRegistry, multi: MultiToolSkill
    ) -> None:
        registry.register(multi)
        missing = registry.get_missing_tools(
            "multi_tool",
            available_tool_keys={"web_search", "calculator", "http_get"},
        )
        assert missing == []

    def test_get_missing_tools_some_missing(
        self, registry: SkillRegistry, multi: MultiToolSkill
    ) -> None:
        registry.register(multi)
        missing = registry.get_missing_tools(
            "multi_tool",
            available_tool_keys={"web_search"},
        )
        assert set(missing) == {"calculator", "http_get"}

    def test_can_execute_true(
        self, registry: SkillRegistry, multi: MultiToolSkill
    ) -> None:
        registry.register(multi)
        assert registry.can_execute(
            "multi_tool",
            available_tool_keys={"web_search", "calculator", "http_get"},
        )

    def test_can_execute_false(
        self, registry: SkillRegistry, multi: MultiToolSkill
    ) -> None:
        registry.register(multi)
        assert not registry.can_execute(
            "multi_tool",
            available_tool_keys={"web_search"},
        )

    def test_no_required_tools_can_always_execute(
        self, registry: SkillRegistry, echo: EchoSkill
    ) -> None:
        registry.register(echo)
        assert registry.can_execute("echo", available_tool_keys=set())

    def test_event_bus_injected_on_register(self, echo: EchoSkill) -> None:
        bus = EventBus()
        registry = SkillRegistry(event_bus=bus)
        registry.register(echo)
        # Le bus doit être injecté dans le skill
        assert echo._event_bus is bus

    def test_set_event_bus_injects_into_existing(
        self, registry: SkillRegistry, echo: EchoSkill
    ) -> None:
        registry.register(echo)
        bus = EventBus()
        registry.set_event_bus(bus)
        assert echo._event_bus is bus

    def test_clear(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        registry.register(echo)
        registry.clear()
        assert len(registry) == 0

    def test_contains(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        assert "echo" not in registry
        registry.register(echo)
        assert "echo" in registry

    def test_repr(self, registry: SkillRegistry, echo: EchoSkill) -> None:
        registry.register(echo)
        assert "echo" in repr(registry)

    def test_register_skill_with_empty_key_raises(
        self, registry: SkillRegistry
    ) -> None:
        class BadSkill(BaseSkill):
            key = "placeholder"  # will be overridden below

            def run(self, **kwargs: Any) -> str:
                return ""  # noqa: E704

        bad = BadSkill()
        bad.__class__.key = ""  # force bad state
        with pytest.raises(ValueError, match="empty key"):
            registry.register(bad)
