"""
AI Engine CLI — provider commands.

    ai-engine provider list
    ai-engine provider add  --name "OpenAI" --type openai --model gpt-4o --key sk-...
    ai-engine provider show <id-or-name>
    ai-engine provider delete <id-or-name>
"""

from __future__ import annotations

from typing import Annotated, Optional

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError("Install with: pip install ai-engine[cli]") from e

from ai_engine.adapters.cli.console import (
    confirm,
    print_provider_detail,
    print_providers_table,
    print_success,
)
from ai_engine.adapters.cli.utils import (
    DEFAULT_DB,
    abort,
    get_storage,
    resolve_provider,
)

app = typer.Typer(
    name="provider",
    help="Manage LLM providers.",
    no_args_is_help=True,
)


@app.command("list")
def provider_list(
    db: Annotated[
        str, typer.Option("--db", envvar="AI_ENGINE_DB", help="Database file")
    ] = DEFAULT_DB,
    active_only: Annotated[
        bool, typer.Option("--active/--all", help="Show only active providers")
    ] = False,
) -> None:
    """List all configured LLM providers."""
    storage = get_storage(db)
    providers = storage.list_providers(is_active=True if active_only else None)
    print_providers_table(providers)


@app.command("add")
def provider_add(
    name: Annotated[
        str, typer.Option("--name", "-n", help="Provider display name", prompt=True)
    ],
    provider_type: Annotated[
        str,
        typer.Option(
            "--type",
            "-t",
            help="Provider type (openai, anthropic, ollama, …)",
            prompt=True,
        ),
    ],
    model: Annotated[
        str, typer.Option("--model", "-m", help="Default model name", prompt=True)
    ],
    key: Annotated[
        Optional[str], typer.Option("--key", "-k", help="API key (or set via env)")
    ] = None,
    base_url: Annotated[
        Optional[str], typer.Option("--base-url", help="Custom API base URL")
    ] = None,
    default: Annotated[
        bool, typer.Option("--default/--no-default", help="Mark as default provider")
    ] = False,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Add a new LLM provider."""
    from ai_engine.models.provider import LLMProviderConfig
    from ai_engine.types import ProviderType
    from pydantic import SecretStr

    # Validate provider_type
    valid_types = [t.value for t in ProviderType]
    if provider_type not in valid_types:
        abort(
            f"Unknown provider type '{provider_type}'. "
            f"Valid types: {', '.join(sorted(valid_types))}"
        )

    storage = get_storage(db)
    provider = LLMProviderConfig(
        name=name,
        provider_type=ProviderType(provider_type),
        default_model=model,
        api_key=SecretStr(key) if key else None,
        api_base_url=base_url,
        is_default=default,
    )
    storage.save_provider(provider)
    print_success(f"Provider '{name}' created with ID {provider.id[:8]}…")
    print_provider_detail(provider)


@app.command("show")
def provider_show(
    identifier: Annotated[str, typer.Argument(help="Provider ID, name, or ID prefix")],
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Show details for a provider."""
    storage = get_storage(db)
    provider = resolve_provider(storage, identifier)
    print_provider_detail(provider)


@app.command("delete")
def provider_delete(
    identifier: Annotated[str, typer.Argument(help="Provider ID, name, or ID prefix")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Delete a provider."""
    storage = get_storage(db)
    provider = resolve_provider(storage, identifier)
    if not yes and not confirm(f"Delete provider '{provider.name}'?"):
        raise typer.Abort()
    storage.delete_provider(provider.id)
    print_success(f"Provider '{provider.name}' deleted.")
