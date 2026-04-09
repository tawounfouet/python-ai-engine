"""
Exemple 05b : Phase 4 — Tools, Skills & Events.

Illustre les nouveaux composants de la Phase 4 :
  1. BaseTool    → créer un tool custom avec événements
  2. Skills      → créer un skill custom qui orchestre des tools
  3. EventBus    → observer les événements du système

Aucune clé API requise — fonctionne entièrement en local.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from ai_engine.events import (
    EventBus,
    SkillCompletedEvent,
    SkillStartedEvent,
    ToolCalledEvent,
    ToolSucceededEvent,
)
from ai_engine.skills import BaseSkill, SkillRegistry
from ai_engine.tools import (
    BaseTool,
    CalculatorTool,
    DuckDuckGoSearchTool,
    ToolExecutor,
    ToolRegistry,
)
from ai_engine.types import EventType, SkillCategory, ToolType


# ── 1. EventBus — observabilité ──────────────────────────────────────────────

print("=" * 60)
print("1. EventBus")
print("=" * 60)

bus = EventBus()


@bus.on(EventType.TOOL_SUCCEEDED)
def on_tool_success(event: ToolSucceededEvent) -> None:
    print(f"  📊 Tool succeeded: {event.tool_name} ({event.duration_ms:.1f}ms)")


@bus.on(EventType.SKILL_STARTED)
def on_skill_start(event: SkillStartedEvent) -> None:
    print(f"  🚀 Skill started: {event.skill_key}")


@bus.on(EventType.SKILL_COMPLETED)
def on_skill_done(event: SkillCompletedEvent) -> None:
    print(f"  ✅ Skill completed: {event.skill_key} ({event.duration_ms:.1f}ms)")


# Émettre un événement manuellement
bus.emit(
    ToolSucceededEvent(tool_name="test_tool", tool_call_id="tc-1", duration_ms=12.5)
)
print()


# ── 2. BaseTool custom ────────────────────────────────────────────────────────

print("=" * 60)
print("2. Custom Tool via BaseTool")
print("=" * 60)


class UppercaseTool(BaseTool):
    key = "uppercase"
    name = "Uppercase"
    description = "Converts text to uppercase."
    parameters_schema = {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    }

    def run(self, text: str, **_: Any) -> str:
        return text.upper()


tool = UppercaseTool()
print(f"Tool: {tool}")
print(f"Result: {tool(text='hello phase 4!')}")
print(f"Schema: {tool.get_function_schema()['function']['name']}")
print()


# ── 3. CalculatorTool intégré ─────────────────────────────────────────────────

print("=" * 60)
print("3. CalculatorTool (built-in)")
print("=" * 60)

calc = CalculatorTool()
expressions = ["2 ** 10", "sqrt(144)", "sin(pi / 2)", "(10 + 5) * 3"]
for expr in expressions:
    print(f"  {expr:25s} = {calc(expression=expr)}")
print()


# ── 4. ToolRegistry avec tools intégrés ──────────────────────────────────────

print("=" * 60)
print("4. ToolRegistry")
print("=" * 60)

registry = ToolRegistry()
calc_tool = CalculatorTool()
upper_tool = UppercaseTool()
registry.register_tool(calc_tool.definition, calc_tool.run)
registry.register_tool(upper_tool.definition, upper_tool.run)

print(f"Registered tools: {registry.keys()}")
print(f"Total: {len(registry)} tools")
print()


# ── 5. BaseSkill custom ───────────────────────────────────────────────────────

print("=" * 60)
print("5. Custom Skill via BaseSkill")
print("=" * 60)


class MathSummarySkill(BaseSkill):
    """Skill de démonstration : évalue plusieurs expressions et résume."""

    key = "math_summary"
    name = "Math Summary"
    description = "Evaluates a list of math expressions and returns a summary."
    category = SkillCategory.DATA
    required_tool_keys = ["calculator"]

    def run(
        self,
        *,
        llm_client: Any,
        expressions: list[str],
        agent_id: str | None = None,
        conversation_id: str | None = None,
        **kwargs: Any,
    ) -> dict[str, str]:
        calc = CalculatorTool()
        results = {expr: calc(expression=expr) for expr in expressions}
        return results


skill = MathSummarySkill(event_bus=bus)
mock_llm = MagicMock()

result = skill.execute(
    llm_client=mock_llm,
    expressions=["2**8", "sqrt(256)", "100 / 7"],
    agent_id="demo-agent",
)
print("Math results:")
for expr, val in result.items():
    print(f"  {expr:15s} = {val}")
print()


# ── 6. SkillRegistry ──────────────────────────────────────────────────────────

print("=" * 60)
print("6. SkillRegistry")
print("=" * 60)

skill_registry = SkillRegistry(event_bus=bus)
skill_registry.register(MathSummarySkill())

# Vérification des tools manquants
missing = skill_registry.get_missing_tools(
    "math_summary", available_tool_keys={"calculator"}
)
print(f"Missing tools for 'math_summary': {missing or 'none'}")

can_run = skill_registry.can_execute("math_summary", available_tool_keys={"calculator"})
print(f"Can execute: {can_run}")

definitions = skill_registry.get_definitions()
print(f"Registered skills: {[d.key for d in definitions]}")
print()

print("=" * 60)
print("✅ Phase 4 demo complete!")
print("   Tools ✓  |  Skills ✓  |  EventBus ✓")
print("=" * 60)
