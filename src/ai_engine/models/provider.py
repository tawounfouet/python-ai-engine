"""
AI Engine Models — Provider (LLM Provider Configuration).

Conversion du modèle Django `Provider` en Pydantic BaseModel pur.
Remplace : django-ai-app/models/provider.py
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field, SecretStr

from ai_engine.types import ProviderType


class ProviderCapabilities(BaseModel):
    """Capacités techniques d'un provider LLM."""

    vision: bool = False
    function_calling: bool = True
    streaming: bool = True
    context_window: int = 4096


class PricingConfig(BaseModel):
    """Configuration tarifaire d'un provider."""

    input_per_1k_tokens: float = 0.0
    output_per_1k_tokens: float = 0.0
    currency: str = "USD"


class ProviderSettings(BaseModel):
    """Paramètres de configuration d'un provider LLM."""

    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = None
    max_retries: int = 2
    timeout: int = 30
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None


class LLMProviderConfig(BaseModel):
    """
    Configuration d'un fournisseur LLM/AI.

    Équivalent standalone du modèle Django `Provider`.

    Usage:
        provider = LLMProviderConfig(
            name="OpenAI GPT-4o",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o",
            api_key="sk-...",
        )
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    provider_type: ProviderType
    description: str = ""

    # Model configuration
    default_model: str = Field(
        ...,
        description="Nom du modèle (ex: gpt-4o, claude-3-opus, llama3)",
    )

    # Credentials — explicites au lieu d'un JSONField opaque
    api_key: SecretStr | None = None
    api_base_url: str | None = None
    extra_secrets: dict[str, str] = Field(default_factory=dict)

    # Configuration
    settings: ProviderSettings = Field(default_factory=ProviderSettings)

    # Capabilities
    capabilities: ProviderCapabilities = Field(default_factory=ProviderCapabilities)

    # Pricing
    pricing: PricingConfig = Field(default_factory=PricingConfig)

    # État
    is_active: bool = True
    is_default: bool = False

    # Metadata
    metadata: dict[str, object] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def get_api_key_value(self) -> str | None:
        """Retourne la valeur de la clé API (déchiffrée)."""
        if self.api_key is None:
            return None
        return self.api_key.get_secret_value()

    def get_secret(self, key: str, default: str = "") -> str:
        """Récupère une valeur depuis extra_secrets."""
        return self.extra_secrets.get(key, default)
