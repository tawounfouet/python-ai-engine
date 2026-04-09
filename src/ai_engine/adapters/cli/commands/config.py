"""
AI Engine CLI — config commands.

    ai-engine config show        — show current runtime config
    ai-engine config set KEY VAL — set a config value (stored as env-override)
"""

from __future__ import annotations

import os
from typing import Annotated

try:
    import typer
    from rich.table import Table
    from rich import box
except ImportError as e:  # pragma: no cover
    raise ImportError("Install with: pip install ai-engine[cli]") from e

from ai_engine.adapters.cli.console import console, print_success
from ai_engine.adapters.cli.utils import DEFAULT_DB

app = typer.Typer(
    name="config",
    help="Show and override runtime configuration.",
    no_args_is_help=True,
)

# Keys that are surfaced to the user
_CONFIG_KEYS = {
    "AI_ENGINE_DB": "Default database file",
    "AI_ENGINE_AGENT": "Default agent (slug or ID)",
    "AI_ENGINE_LOG_LEVEL": "Logging level (DEBUG, INFO, WARNING, ERROR)",
}


@app.command("show")
def config_show(
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Display the current effective configuration."""
    table = Table(
        title="AI Engine — Runtime Config",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("Key", style="bold cyan")
    table.add_column("Value")
    table.add_column("Description", style="dim")

    # Extra: DB path
    table.add_row("AI_ENGINE_DB", db, "Database file (active)")

    for key, description in _CONFIG_KEYS.items():
        if key == "AI_ENGINE_DB":
            continue  # already shown above
        value = os.environ.get(key, "[dim](not set)[/dim]")
        table.add_row(key, value, description)

    console.print(table)


@app.command("set")
def config_set(
    key: Annotated[
        str, typer.Argument(help=f"Config key. Known keys: {', '.join(_CONFIG_KEYS)}")
    ],
    value: Annotated[str, typer.Argument(help="Value to assign")],
) -> None:
    """
    Print an export statement for a config key.

    Because child processes cannot modify the parent shell environment,
    this command prints the export command you can eval or copy.
    """
    if key not in _CONFIG_KEYS:
        known = ", ".join(_CONFIG_KEYS.keys())
        typer.echo(
            f"Warning: '{key}' is not a known config key. Known keys: {known}", err=True
        )

    export_cmd = f"export {key}={value!r}"
    console.print(
        f"\nRun the following command in your shell:\n\n  [bold cyan]{export_cmd}[/bold cyan]\n"
    )
    print_success(f"Or add it to your ~/.zshrc / ~/.bashrc for persistence.")
