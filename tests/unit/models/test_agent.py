"""Tests unitaires pour ai_engine.models.agent."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from ai_engine import Agent, AgentConfig, AgentRole, LLMProviderConfig


class TestAgentConfig:
    def test_defaults(self) -> None:
        config = AgentConfig()
        assert config.max_iterations == 10
        assert config.max_tokens_per_run == 8000
        assert config.temperature is None
        assert config.max_tokens_per_response is None
        assert config.enable_memory is True
        assert config.enable_tools is True
        assert config.enable_rag is False
        assert config.retry_on_failure is True
        assert config.max_retries == 3
        assert config.extra == {}

    def test_custom_values(self) -> None:
        config = AgentConfig(
            max_iterations=20,
            temperature=0.5,
            enable_rag=True,
            extra={"custom_key": "value"},
        )
        assert config.max_iterations == 20
        assert config.temperature == 0.5
        assert config.enable_rag is True
        assert config.extra["custom_key"] == "value"

    def test_max_iterations_validation(self) -> None:
        with pytest.raises(ValidationError):
            AgentConfig(max_iterations=0)
        with pytest.raises(ValidationError):
            AgentConfig(max_iterations=-1)
        AgentConfig(max_iterations=1)  # valid minimum

    def test_temperature_bounds(self) -> None:
        AgentConfig(temperature=0.0)
        AgentConfig(temperature=2.0)
        with pytest.raises(ValidationError):
            AgentConfig(temperature=-0.1)
        with pytest.raises(ValidationError):
            AgentConfig(temperature=2.1)

    def test_json_roundtrip(self) -> None:
        config = AgentConfig(max_iterations=15, temperature=0.9)
        data = config.model_dump()
        restored = AgentConfig.model_validate(data)
        assert restored == config


class TestAgent:
    def test_creation_minimal(self, provider: LLMProviderConfig) -> None:
        agent = Agent(
            name="Assistant",
            provider_id=provider.id,
        )
        assert agent.name == "Assistant"
        assert agent.provider_id == provider.id
        assert agent.role == AgentRole.ASSISTANT
        assert agent.id  # uuid auto
        assert agent.is_active is True
        assert agent.slug == ""
        assert agent.tool_ids == []
        assert agent.skill_ids == []
        assert agent.knowledge_base_ids == []

    def test_creation_full(self, provider: LLMProviderConfig) -> None:
        agent = Agent(
            name="Research Bot",
            slug="research-bot",
            description="A research agent",
            role=AgentRole.RESEARCHER,
            provider_id=provider.id,
            model="gpt-4o-mini",
            system_prompt="You are a researcher.",
            welcome_message="Hello!",
            config=AgentConfig(max_iterations=20, enable_rag=True),
            tool_ids=["tool-1", "tool-2"],
            skill_ids=["skill-1"],
            knowledge_base_ids=["kb-1"],
            owner_id="user-123",
            metadata={"team": "research"},
        )
        assert agent.role == AgentRole.RESEARCHER
        assert agent.model == "gpt-4o-mini"
        assert agent.config.max_iterations == 20
        assert agent.config.enable_rag is True
        assert len(agent.tool_ids) == 2
        assert agent.owner_id == "user-123"

    def test_unique_ids(self, provider: LLMProviderConfig) -> None:
        a1 = Agent(name="A1", provider_id=provider.id)
        a2 = Agent(name="A2", provider_id=provider.id)
        assert a1.id != a2.id

    def test_required_provider_id(self) -> None:
        with pytest.raises(ValidationError):
            Agent(name="No Provider")  # type: ignore[call-arg]

    def test_get_effective_temperature(self, provider: LLMProviderConfig) -> None:
        # No override
        agent = Agent(name="A", provider_id=provider.id)
        assert agent.get_effective_temperature() is None

        # With override
        agent2 = Agent(
            name="B",
            provider_id=provider.id,
            config=AgentConfig(temperature=0.3),
        )
        assert agent2.get_effective_temperature() == 0.3

    def test_all_roles(self) -> None:
        for role in AgentRole:
            assert isinstance(role.value, str)

    def test_json_serialization(self, provider: LLMProviderConfig) -> None:
        agent = Agent(
            name="Test",
            slug="test",
            provider_id=provider.id,
            role=AgentRole.CODER,
            tool_ids=["t1", "t2"],
        )
        json_str = agent.model_dump_json()
        data = json.loads(json_str)
        assert data["name"] == "Test"
        assert data["role"] == "coder"
        assert data["tool_ids"] == ["t1", "t2"]

    def test_model_dump_roundtrip(self, provider: LLMProviderConfig) -> None:
        agent = Agent(
            name="Roundtrip",
            provider_id=provider.id,
            config=AgentConfig(max_iterations=5),
        )
        data = agent.model_dump()
        restored = Agent.model_validate(data)
        assert restored.name == agent.name
        assert restored.id == agent.id
        assert restored.config.max_iterations == 5

    def test_timestamps_utc(self, provider: LLMProviderConfig) -> None:
        agent = Agent(name="Test", provider_id=provider.id)
        assert agent.created_at.tzinfo is not None
        assert agent.updated_at.tzinfo is not None
