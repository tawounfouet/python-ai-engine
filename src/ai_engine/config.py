"""
AI Engine — Configuration globale.

Utilise Pydantic Settings pour la gestion des variables d'environnement.
Toutes les variables sont préfixées par `AI_ENGINE_`.

Usage:
    from ai_engine.config import get_settings

    settings = get_settings()
    print(settings.default_provider)
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration globale du package ai_engine."""

    model_config = SettingsConfigDict(
        env_prefix="AI_ENGINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── General ──
    debug: bool = False
    log_level: str = "INFO"

    # ── Default Provider ──
    default_provider_type: str = "openai"
    default_model: str = "gpt-4o"

    # ── API Keys (convenience — can also be set per-provider) ──
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # ── Storage ──
    default_storage: str = "memory"  # "memory", "sqlite", "json", "sqlalchemy"
    sqlite_db_path: str = "ai_engine.db"
    json_storage_path: str = "ai_engine_data/"

    # ── Execution ──
    max_tool_iterations: int = 10
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    default_max_tokens: int = 4096
    default_timeout: int = 30


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Retourne l'instance singleton des settings."""
    return Settings()
