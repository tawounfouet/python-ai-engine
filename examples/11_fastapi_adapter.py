"""
Example 11 — FastAPI Adapter
=============================

Montre comment intégrer ai_engine dans une app FastAPI existante.
Deux modes sont démontrés :

1. **Montage minimal** — `create_router()` avec un simple fichier SQLite
2. **Montage avancé** — storage custom, prefix, tags OpenAPI, exception handlers

Run with:
    uv run uvicorn examples.11_fastapi_adapter:app --reload

Puis ouvrir : http://localhost:8000/docs
"""

from __future__ import annotations

from fastapi import FastAPI

from ai_engine.adapters.fastapi import create_router
from ai_engine.adapters.fastapi.exception_handlers import register_handlers

# ── App FastAPI ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI Engine — FastAPI Demo",
    description=(
        "Démonstration de l'intégration de `ai_engine` dans FastAPI.\n\n"
        "Tous les endpoints CRUD (providers, agents, conversations) "
        "et l'endpoint de chat sont exposés ici."
    ),
    version="0.5.2",
)

# ── Enregistrer les exception handlers domain → HTTP ────────────────────────

register_handlers(app)

# ── Monter le router ai_engine ────────────────────────────────────────────────

# Option 1 : base de données par défaut (AI_ENGINE_DB ou ai_engine.db)
app.include_router(
    create_router(),
    prefix="/api/v1",
)

# Option 2 (commentée) : storage custom, DB explicite, tags préfixés
# from ai_engine.storage.sqlite import SQLiteStorage
# storage = SQLiteStorage("prod.db")
# app.include_router(
#     create_router(storage=storage, tags_prefix="AI"),
#     prefix="/api/v1/ai",
# )


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Seed data pour la démo ────────────────────────────────────────────────────

@app.on_event("startup")
def seed_demo_data() -> None:
    """Crée un provider et un agent de démo au démarrage si absents."""
    from ai_engine.models.agent import Agent, AgentConfig
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.storage.sqlite import SQLiteStorage
    from ai_engine.types import AgentRole, ProviderType
    from pydantic import SecretStr
    import os

    db_path = os.environ.get("AI_ENGINE_DB", "ai_engine.db")
    storage = SQLiteStorage(db_path)

    if not storage.list_providers():
        provider = LLMProviderConfig(
            name="OpenAI (demo)",
            provider_type=ProviderType.OPENAI,
            default_model="gpt-4o-mini",
            api_key=SecretStr("sk-demo-key-not-real"),
            is_default=True,
        )
        storage.save_provider(provider)

        agent = Agent(
            name="Demo Assistant",
            slug="demo-assistant",
            provider_id=provider.id,
            system_prompt="You are a concise, helpful assistant.",
            role=AgentRole.ASSISTANT,
            config=AgentConfig(),
        )
        storage.save_agent(agent)
        print(f"✅ Demo data seeded (DB: {db_path})")
