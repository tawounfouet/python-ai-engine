"""
AI Engine CLI — agent commands.

    ai-engine agent list
    ai-engine agent create --name "My Agent" --provider <id> --prompt "You are…"
    ai-engine agent show <id-or-slug>
    ai-engine agent delete <id-or-slug>
"""

from __future__ import annotations

from typing import Annotated, Optional

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError("Install with: pip install ai-engine[cli]") from e

from ai_engine.adapters.cli.console import (
    confirm,
    print_agent_detail,
    print_agents_table,
    print_success,
)
from ai_engine.adapters.cli.utils import (
    DEFAULT_DB,
    abort,
    get_storage,
    resolve_agent,
    resolve_provider,
)

app = typer.Typer(
    name="agent",
    help="Manage AI agents.",
    no_args_is_help=True,
)


@app.command("list")
def agent_list(
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
    active_only: Annotated[
        bool, typer.Option("--active/--all", help="Show only active agents")
    ] = False,
) -> None:
    """List all agents."""
    storage = get_storage(db)
    agents = storage.list_agents(is_active=True if active_only else None)
    print_agents_table(agents)


@app.command("create")
def agent_create(
    name: Annotated[str, typer.Option("--name", "-n", help="Agent name", prompt=True)],
    provider: Annotated[
        str,
        typer.Option(
            "--provider", "-p", help="Provider ID, name, or prefix", prompt=True
        ),
    ],
    prompt: Annotated[str, typer.Option("--prompt", help="System prompt")] = "",
    role: Annotated[str, typer.Option("--role", "-r", help="Agent role")] = "assistant",
    slug: Annotated[
        Optional[str],
        typer.Option("--slug", help="Custom slug (auto-generated if omitted)"),
    ] = None,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Create a new agent."""
    from ai_engine.types import AgentRole

    valid_roles = [r.value for r in AgentRole]
    if role not in valid_roles:
        abort(f"Unknown role '{role}'. Valid roles: {', '.join(valid_roles)}")

    storage = get_storage(db)
    prov = resolve_provider(storage, provider)

    from ai_engine.services.agent import AgentService

    svc = AgentService(storage)
    agent = svc.create_agent(
        name=name,
        provider_id=prov.id,
        system_prompt=prompt,
        role=AgentRole(role),
        slug=slug,
    )
    print_success(f"Agent '{name}' created with ID {agent.id[:8]}…")
    print_agent_detail(agent, prov)


@app.command("show")
def agent_show(
    identifier: Annotated[str, typer.Argument(help="Agent ID, slug, or ID prefix")],
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Show details for an agent."""
    storage = get_storage(db)
    agent = resolve_agent(storage, identifier)
    provider = storage.get_provider(agent.provider_id)
    print_agent_detail(agent, provider)


@app.command("delete")
def agent_delete(
    identifier: Annotated[str, typer.Argument(help="Agent ID, slug, or ID prefix")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Delete an agent."""
    storage = get_storage(db)
    agent = resolve_agent(storage, identifier)
    if not yes and not confirm(f"Delete agent '{agent.name}'?"):
        raise typer.Abort()
    storage.delete_agent(agent.id)
    print_success(f"Agent '{agent.name}' deleted.")
