"""
Example 10 — CLI Adapter
========================

This file demonstrates everything exposed by `ai-engine` from the terminal.
It does NOT execute real LLM calls — it creates sample data in a temp DB
so you can see the CLI in action without any API keys.

Run with:
    uv run python examples/10_cli_adapter.py

Then try the CLI yourself:
    ai-engine --help
    ai-engine provider list
    ai-engine agent list
    ai-engine chat --agent demo-assistant --once "Say hello"
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from ai_engine.adapters.cli import app

_runner = CliRunner()


# ── Helpers ───────────────────────────────────────────────────────────────────


def run(args: list[str], db: str) -> None:
    """Invoke an ai-engine CLI command in-process and print its output."""
    print(f"\n$ ai-engine {' '.join(args)}")
    print("-" * 60)
    # Inject AI_ENGINE_DB via env so every command picks it up
    env_patch = {**os.environ, "AI_ENGINE_DB": db}
    result = _runner.invoke(app, args, env=env_patch)
    # Strip trailing blank line added by CliRunner but keep the rest
    output = result.output.rstrip("\n")
    if output:
        print(output)
    if result.exit_code not in (0, 1):
        print(f"[exit {result.exit_code}]")
    if result.exception and result.exit_code not in (0, 1):
        import traceback

        traceback.print_exception(
            type(result.exception), result.exception, result.exception.__traceback__
        )


# ── Seed data (direct API, no LLM) ───────────────────────────────────────────


def seed_database(db_path: str) -> tuple[Any, Any]:
    """Populate the temp DB with a provider and an agent."""
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.models.agent import Agent, AgentConfig
    from ai_engine.storage.sqlite import SQLiteStorage
    from ai_engine.types import AgentRole, ProviderType
    from pydantic import SecretStr

    storage = SQLiteStorage(db_path)

    # Provider
    provider = LLMProviderConfig(
        name="OpenAI (demo)",
        provider_type=ProviderType.OPENAI,
        default_model="gpt-4o-mini",
        api_key=SecretStr("sk-demo-key-not-real"),
        is_default=True,
    )
    storage.save_provider(provider)

    # Agent
    agent = Agent(
        name="Demo Assistant",
        slug="demo-assistant",
        provider_id=provider.id,
        system_prompt="You are a concise, helpful assistant.",
        role=AgentRole.ASSISTANT,
        config=AgentConfig(),
    )
    storage.save_agent(agent)

    print(f"✅  Seeded DB: {db_path}")
    print(f"    Provider : {provider.name}  ({provider.id[:8]}…)")
    print(f"    Agent    : {agent.name}  slug={agent.slug!r}  ({agent.id[:8]}…)")
    return provider, agent


# ── Main demo ─────────────────────────────────────────────────────────────────


def main() -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db = f.name

    print("=" * 60)
    print(" AI Engine CLI — Demo (temp DB, no real API calls)")
    print("=" * 60)

    provider, agent = seed_database(db)

    run(["--version"], db)
    run(["provider", "list"], db)
    run(["provider", "show", provider.id[:8]], db)
    run(["agent", "list"], db)
    run(["agent", "show", "demo-assistant"], db)
    run(["conversation", "list"], db)
    run(["config", "show"], db)

    print("\n" + "=" * 60)
    print(" To start a real interactive chat session:")
    print(f"   AI_ENGINE_DB={db} ai-engine chat --agent demo-assistant")
    print("=" * 60)

    Path(db).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
