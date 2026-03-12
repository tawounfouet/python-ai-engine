"""Tests unitaires pour ai_engine.models.provider."""

from __future__ import annotations

import json

import pytest
from pydantic import SecretStr, ValidationError

from ai_engine import (
    LLMProviderConfig,
    PricingConfig,
    ProviderCapabilities,
    ProviderSettings,
    ProviderType,
)


class TestProviderCapabilities:
    def test_defaults(self) -> None:
        caps = ProviderCapabilities()
        assert caps.vision is False
        assert caps.function_calling is True
        assert caps.streaming is True
        assert caps.context_window == 4096

    def test_custom_values(self) -> None:
        caps = ProviderCapabilities(vision=True, context_window=128000)
        assert caps.vision is True
        assert caps.context_window == 128000

    def test_json_roundtrip(self) -> None:
        caps = ProviderCapabilities(vision=True, context_window=32000)
        data = caps.model_dump()
        restored = ProviderCapabilities.model_validate(data)
        assert restored == caps


class TestPricingConfig:
    def test_defaults(self) -> None:
        pricing = PricingConfig()
        assert pricing.input_per_1k_tokens == 0.0
        assert pricing.output_per_1k_tokens == 0.0
        assert pricing.currency == "USD"

    def test_custom_pricing(self) -> None:
        pricing = PricingConfig(
            input_per_1k_tokens=0.01,
            output_per_1k_tokens=0.03,
            currency="EUR",
        )
        assert pricing.input_per_1k_tokens == 0.01
        assert pricing.currency == "EUR"


class TestProviderSettings:
    def test_defaults(self) -> None:
        settings = ProviderSettings()
        assert settings.temperature == 0.7
        assert settings.max_tokens is None
        assert settings.max_retries == 2
        assert settings.timeout == 30

    def test_temperature_bounds(self) -> None:
        # Valid bounds
        ProviderSettings(temperature=0.0)
        ProviderSettings(temperature=2.0)

        # Out of bounds
        with pytest.raises(ValidationError):
            ProviderSettings(temperature=-0.1)
        with pytest.raises(ValidationError):
            ProviderSettings(temperature=2.1)


class TestLLMProviderConfig:
    def test_creation_minimal(self) -> None:
        provider = LLMProviderConfig(
            name="OpenAI",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
        )
        assert provider.name == "OpenAI"
        assert provider.provider_type == ProviderType.OPENAI
        assert provider.default_model == "gpt-4o"
        assert provider.id  # uuid generated
        assert provider.is_active is True
        assert provider.is_default is False

    def test_creation_full(self) -> None:
        provider = LLMProviderConfig(
            name="OpenAI GPT-4o",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            description="Test provider",
            api_key="sk-test123",
            api_base_url="https://api.openai.com/v1",
            extra_secrets={"org_id": "org-123"},
            settings=ProviderSettings(temperature=0.5, max_tokens=1000),
            capabilities=ProviderCapabilities(vision=True, context_window=128000),
            pricing=PricingConfig(input_per_1k_tokens=0.01, output_per_1k_tokens=0.03),
            is_active=True,
            is_default=True,
            metadata={"tier": "premium"},
        )
        assert provider.description == "Test provider"
        assert provider.is_default is True
        assert provider.settings.temperature == 0.5
        assert provider.capabilities.vision is True
        assert provider.pricing.input_per_1k_tokens == 0.01
        assert provider.metadata["tier"] == "premium"

    def test_id_auto_generated(self) -> None:
        p1 = LLMProviderConfig(name="P1", provider_type=ProviderType.OPENAI, default_model="gpt-4o")
        p2 = LLMProviderConfig(name="P2", provider_type=ProviderType.OPENAI, default_model="gpt-4o")
        assert p1.id != p2.id
        assert len(p1.id) == 36  # UUID format

    def test_api_key_is_secret(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            api_key="sk-secret-value",
        )
        # SecretStr should not reveal value in repr
        assert "sk-secret-value" not in repr(provider.api_key)
        assert isinstance(provider.api_key, SecretStr)

    def test_get_api_key_value(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            api_key="sk-secret-value",
        )
        assert provider.get_api_key_value() == "sk-secret-value"

    def test_get_api_key_value_none(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OLLAMA,
            default_model="llama3",
        )
        assert provider.get_api_key_value() is None

    def test_get_secret(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            extra_secrets={"org_id": "org-123"},
        )
        assert provider.get_secret("org_id") == "org-123"
        assert provider.get_secret("missing") == ""
        assert provider.get_secret("missing", "default") == "default"

    def test_required_fields(self) -> None:
        with pytest.raises(ValidationError):
            LLMProviderConfig(name="Test", provider_type=ProviderType.OPENAI)  # type: ignore[call-arg]

    def test_json_serialization(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            api_key="sk-secret",
        )
        json_str = provider.model_dump_json()
        data = json.loads(json_str)
        assert data["name"] == "Test"
        assert data["provider_type"] == "openai"
        # SecretStr is serialized as '**********' by default
        assert data["api_key"] == "**********"

    def test_model_dump_roundtrip(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.ANTHROPIC,
            default_model="claude-3-opus",
            capabilities=ProviderCapabilities(vision=True),
        )
        data = provider.model_dump()
        # Remove api_key since SecretStr roundtrip needs special handling
        data.pop("api_key", None)
        restored = LLMProviderConfig.model_validate(data)
        assert restored.name == provider.name
        assert restored.provider_type == provider.provider_type
        assert restored.capabilities.vision is True

    def test_timestamps(self) -> None:
        provider = LLMProviderConfig(
            name="Test",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
        )
        assert provider.created_at is not None
        assert provider.updated_at is not None
        assert provider.created_at.tzinfo is not None  # UTC-aware

    def test_all_provider_types(self) -> None:
        """Vérifie que tous les ProviderType sont des str valides."""
        for pt in ProviderType:
            assert isinstance(pt.value, str)
            assert len(pt.value) > 0
