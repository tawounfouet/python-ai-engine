"""Tests unitaires pour ai_engine.models.skill."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai_engine import AgentSkillAssignment, Proficiency, Skill, SkillCategory


class TestSkill:
    def test_creation_minimal(self) -> None:
        skill = Skill(key="research", name="Research")
        assert skill.key == "research"
        assert skill.name == "Research"
        assert skill.category == SkillCategory.CUSTOM
        assert skill.is_active is True
        assert skill.required_tool_ids == []
        assert skill.recommended_provider_id is None
        assert skill.config == {}

    def test_creation_full(self) -> None:
        skill = Skill(
            key="coding",
            name="Coding Skill",
            description="Write and review code",
            category=SkillCategory.CODING,
            system_prompt="You are an expert coder.",
            required_tool_ids=["tool-1", "tool-2"],
            config={"max_file_size": 10000},
            recommended_provider_id="provider-123",
            metadata={"version": "1.0"},
        )
        assert skill.category == SkillCategory.CODING
        assert skill.system_prompt == "You are an expert coder."
        assert len(skill.required_tool_ids) == 2
        assert skill.recommended_provider_id == "provider-123"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            Skill(name="No Key")  # type: ignore[call-arg]

    def test_all_categories(self) -> None:
        for cat in SkillCategory:
            skill = Skill(key=f"test_{cat.value}", name=f"Test {cat.value}", category=cat)
            assert skill.category == cat

    def test_json_roundtrip(self) -> None:
        skill = Skill(
            key="data",
            name="Data Skill",
            category=SkillCategory.DATA,
            required_tool_ids=["t1"],
        )
        data = skill.model_dump()
        restored = Skill.model_validate(data)
        assert restored.key == skill.key
        assert restored.id == skill.id
        assert restored.required_tool_ids == ["t1"]


class TestAgentSkillAssignment:
    def test_creation_minimal(self) -> None:
        assignment = AgentSkillAssignment(
            agent_id="agent-1",
            skill_id="skill-1",
        )
        assert assignment.agent_id == "agent-1"
        assert assignment.skill_id == "skill-1"
        assert assignment.proficiency == Proficiency.INTERMEDIATE
        assert assignment.enabled is True
        assert assignment.provider_override_id is None

    def test_creation_full(self) -> None:
        assignment = AgentSkillAssignment(
            agent_id="agent-1",
            skill_id="skill-1",
            provider_override_id="provider-alt",
            proficiency=Proficiency.EXPERT,
            enabled=False,
        )
        assert assignment.proficiency == Proficiency.EXPERT
        assert assignment.enabled is False
        assert assignment.provider_override_id == "provider-alt"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            AgentSkillAssignment(agent_id="agent-1")  # type: ignore[call-arg]
        with pytest.raises(ValidationError):
            AgentSkillAssignment(skill_id="skill-1")  # type: ignore[call-arg]

    def test_all_proficiency_levels(self) -> None:
        for prof in Proficiency:
            assignment = AgentSkillAssignment(
                agent_id="a",
                skill_id="s",
                proficiency=prof,
            )
            assert assignment.proficiency == prof

    def test_json_roundtrip(self) -> None:
        assignment = AgentSkillAssignment(
            agent_id="agent-1",
            skill_id="skill-1",
            proficiency=Proficiency.ADVANCED,
        )
        data = assignment.model_dump()
        restored = AgentSkillAssignment.model_validate(data)
        assert restored.id == assignment.id
        assert restored.proficiency == Proficiency.ADVANCED
