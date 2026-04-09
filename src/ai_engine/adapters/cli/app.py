"""
AI Engine CLI — Root Typer application.

Registers all sub-apps and provides the global --db / --version options.

Entry-point (pyproject.toml):
    [project.scripts]
    ai-engine = "ai_engine.adapters.cli:app"
"""

from __future__ import annotations

from typing import Annotated, Optional

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "CLI adapter requires 'typer'. Install with: pip install ai-engine[cli]"
    ) from e

from ai_engine.adapters.cli.commands.agent import app as agent_app
from ai_engine.adapters.cli.commands.chat import app as chat_app
from ai_engine.adapters.cli.commands.config import app as config_app
from ai_engine.adapters.cli.commands.conversation import app as conversation_app
from ai_engine.adapters.cli.commands.provider import app as provider_app

# ── Root app ──────────────────────────────────────────────────────────────────

app = typer.Typer(
    name="ai-engine",
    help=(
        "AI Engine — multi-provider agent orchestration engine.\n\n"
        "Manage providers, agents, conversations, and chat — all from the terminal."
    ),
    no_args_is_help=True,
    rich_markup_mode="rich",
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

# ── Sub-apps ──────────────────────────────────────────────────────────────────

app.add_typer(provider_app, name="provider")
app.add_typer(agent_app, name="agent")
app.add_typer(conversation_app, name="conversation")
# chat is registered via add_typer so its callback becomes the default command
app.add_typer(chat_app, name="chat")
app.add_typer(config_app, name="config")

# ── Version callback ──────────────────────────────────────────────────────────


def _version_callback(value: bool) -> None:
    if value:
        try:
            from importlib.metadata import version

            v = version("ai-engine")
        except Exception:
            v = "dev"
        typer.echo(f"ai-engine {v}")
        raise typer.Exit(0)


@app.callback()
def _root_callback(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            "-V",
            help="Show version and exit.",
            callback=_version_callback,
            is_eager=True,
        ),
    ] = None,
) -> None:
    """AI Engine CLI — run ai-engine --help for available commands."""
