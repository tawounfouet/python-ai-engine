"""
Factory pour créer les clients LLM selon le type de provider.

Usage:
    client = get_llm_client(provider_config)
    response = client.complete(request)
"""

from __future__ import annotations

from ai_engine.exceptions import AIEngineError
from ai_engine.models.provider import LLMProviderConfig
from ai_engine.services.llm.base import LLMClient
from ai_engine.types import ProviderType


class UnsupportedProviderError(AIEngineError):
    """Erreur levée quand un type de provider n'est pas supporté."""

    pass


def get_llm_client(provider_config: LLMProviderConfig) -> LLMClient:
    """
    Factory pour créer un client LLM selon le type de provider.

    Args:
        provider_config: Configuration du provider LLM

    Returns:
        Instance du client LLM approprié

    Raises:
        UnsupportedProviderError: Si le type de provider n'est pas supporté
        ImportError: Si les dépendances pour le provider ne sont pas installées
    """
    try:
        if provider_config.provider_type == ProviderType.OPENAI:
            from ai_engine.services.llm.openai import OpenAIClient

            return OpenAIClient(provider_config)

        elif provider_config.provider_type == ProviderType.ANTHROPIC:
            from ai_engine.services.llm.anthropic import AnthropicClient

            return AnthropicClient(provider_config)

        elif provider_config.provider_type == ProviderType.OLLAMA:
            from ai_engine.services.llm.ollama import OllamaClient

            return OllamaClient(provider_config)

        elif provider_config.provider_type == ProviderType.CUSTOM:
            # Pour les providers custom, on pourrait avoir une logique différente
            # ou déléguer à un registry de providers personnalisés
            raise UnsupportedProviderError(
                f"Custom providers must be registered separately. "
                f"Provider: {provider_config.name}"
            )

        else:
            raise UnsupportedProviderError(
                f"Unsupported provider type: {provider_config.provider_type}. "
                f"Supported types: {', '.join(t.value for t in [ProviderType.OPENAI, ProviderType.ANTHROPIC, ProviderType.OLLAMA])}"
            )

    except ImportError as e:
        # Reformater l'erreur pour être plus claire
        provider_name = provider_config.provider_type.value
        raise ImportError(
            f"Missing dependencies for {provider_name} provider. "
            f"Install with: pip install ai-engine[{provider_name}] "
            f"or pip install ai-engine[all]. Original error: {e}"
        ) from e


def list_available_providers() -> list[ProviderType]:
    """
    Liste les types de providers disponibles (avec dépendances installées).

    Returns:
        Liste des types de providers utilisables
    """
    available = []

    # Test chaque provider
    test_configs = {
        ProviderType.OPENAI: LLMProviderConfig(
            name="test-openai",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4",
        ),
        ProviderType.ANTHROPIC: LLMProviderConfig(
            name="test-anthropic",
            provider_type=ProviderType.ANTHROPIC,
            default_model="claude-3-opus-20240229",
        ),
        ProviderType.OLLAMA: LLMProviderConfig(
            name="test-ollama",
            provider_type=ProviderType.OLLAMA,
            default_model="llama3",
        ),
    }

    for provider_type, config in test_configs.items():
        try:
            get_llm_client(config)
            available.append(provider_type)
        except (ImportError, UnsupportedProviderError):
            continue

    return available
