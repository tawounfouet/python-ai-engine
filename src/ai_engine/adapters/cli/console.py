"""
AI Engine CLI — Console helpers (Rich).

Toutes les fonctions d'affichage Rich centralisées ici.
Aucun import de typer dans ce module — uniquement rich.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Confirm, Prompt
    from rich.table import Table
    from rich.text import Text
    from rich import box
except ImportError as e:  # pragma: no cover
    raise ImportError(
        "CLI adapter requires 'rich'. Install with: pip install ai-engine[cli]"
    ) from e

console = Console()
err_console = Console(stderr=True)


# ── Helpers génériques ────────────────────────────────────────────────────────


def print_success(msg: str) -> None:
    console.print(f"[bold green]✅ {msg}[/bold green]")


def print_error(msg: str) -> None:
    err_console.print(f"[bold red]❌ {msg}[/bold red]")


def print_warning(msg: str) -> None:
    console.print(f"[bold yellow]⚠️  {msg}[/bold yellow]")


def print_info(msg: str) -> None:
    console.print(f"[dim]{msg}[/dim]")


def print_header(title: str, subtitle: str = "") -> None:
    content = f"[bold cyan]{title}[/bold cyan]"
    if subtitle:
        content += f"\n[dim]{subtitle}[/dim]"
    console.print(Panel(content, box=box.ROUNDED, border_style="cyan"))


# ── Tables ────────────────────────────────────────────────────────────────────


def _fmt_date(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def print_providers_table(providers: list[Any]) -> None:
    if not providers:
        print_warning("No providers found.")
        return

    table = Table(
        title="LLM Providers",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Name", style="bold")
    table.add_column("Type", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Active", justify="center")
    table.add_column("Created", style="dim")

    for p in providers:
        table.add_row(
            p.id[:8] + "…",
            p.name,
            p.provider_type,
            p.default_model,
            "✅" if p.is_active else "❌",
            _fmt_date(p.created_at),
        )
    console.print(table)


def print_agents_table(agents: list[Any]) -> None:
    if not agents:
        print_warning("No agents found.")
        return

    table = Table(
        title="Agents",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Name", style="bold")
    table.add_column("Slug", style="cyan")
    table.add_column("Role", style="green")
    table.add_column("Active", justify="center")
    table.add_column("Created", style="dim")

    for a in agents:
        table.add_row(
            a.id[:8] + "…",
            a.name,
            a.slug or "—",
            a.role,
            "✅" if a.is_active else "❌",
            _fmt_date(a.created_at),
        )
    console.print(table)


def print_conversations_table(conversations: list[Any]) -> None:
    if not conversations:
        print_warning("No conversations found.")
        return

    table = Table(
        title="Conversations",
        box=box.ROUNDED,
        show_lines=False,
        header_style="bold magenta",
    )
    table.add_column("ID", style="dim", max_width=12)
    table.add_column("Title", style="bold")
    table.add_column("Status", style="cyan")
    table.add_column("Messages", justify="right", style="green")
    table.add_column("Last Message", style="dim")

    for c in conversations:
        table.add_row(
            c.id[:8] + "…",
            c.title or "(no title)",
            c.status,
            str(c.message_count),
            _fmt_date(c.last_message_at),
        )
    console.print(table)


def print_messages(messages: list[Any], *, show_meta: bool = False) -> None:
    """Affiche l'historique d'une conversation de façon lisible."""
    if not messages:
        print_warning("No messages.")
        return

    for msg in messages:
        role = msg.role.upper()
        if role == "USER":
            style = "bold blue"
            icon = "👤"
        elif role == "ASSISTANT":
            style = "bold green"
            icon = "🤖"
        elif role == "SYSTEM":
            style = "dim"
            icon = "⚙️ "
        else:
            style = "yellow"
            icon = "🔧"

        header = Text(f"{icon} {role}", style=style)
        if show_meta and msg.created_at:
            header.append(f"  [{_fmt_date(msg.created_at)}]", style="dim")

        console.print(header)
        console.print(Markdown(msg.content) if role == "ASSISTANT" else msg.content)
        console.print()


def print_agent_detail(agent: Any, provider: Any | None = None) -> None:
    lines = [
        f"[bold]ID[/bold]          {agent.id}",
        f"[bold]Name[/bold]        {agent.name}",
        f"[bold]Slug[/bold]        {agent.slug or '—'}",
        f"[bold]Role[/bold]        {agent.role}",
        f"[bold]Active[/bold]      {'Yes' if agent.is_active else 'No'}",
        f"[bold]Provider ID[/bold] {agent.provider_id}",
    ]
    if provider:
        lines.append(
            f"[bold]Provider[/bold]    {provider.name} ({provider.provider_type} / {provider.default_model})"
        )
    if agent.system_prompt:
        lines.append(
            f"\n[bold]System Prompt[/bold]\n[dim]{agent.system_prompt[:300]}[/dim]"
        )

    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold cyan]Agent: {agent.name}[/bold cyan]",
            box=box.ROUNDED,
            border_style="cyan",
        )
    )


def print_provider_detail(provider: Any) -> None:
    lines = [
        f"[bold]ID[/bold]           {provider.id}",
        f"[bold]Name[/bold]         {provider.name}",
        f"[bold]Type[/bold]         {provider.provider_type}",
        f"[bold]Model[/bold]        {provider.default_model}",
        f"[bold]Active[/bold]       {'Yes' if provider.is_active else 'No'}",
        f"[bold]API Key[/bold]      {'set' if provider.api_key else 'not set'}",
        f"[bold]Base URL[/bold]     {provider.api_base_url or '(default)'}",
    ]
    console.print(
        Panel(
            "\n".join(lines),
            title=f"[bold magenta]Provider: {provider.name}[/bold magenta]",
            box=box.ROUNDED,
            border_style="magenta",
        )
    )


# ── Chat UI ───────────────────────────────────────────────────────────────────


def chat_user_prompt(agent_name: str) -> str:
    """Lit la saisie de l'utilisateur dans le mode chat interactif."""
    return Prompt.ask(f"[bold blue]You[/bold blue]")


def chat_print_response(content: str, model: str | None = None) -> None:
    label = f"🤖 Assistant" + (f" [dim]({model})[/dim]" if model else "")
    console.print(f"[bold green]{label}[/bold green]")
    console.print(Markdown(content))
    console.print()


def confirm(msg: str, default: bool = False) -> bool:
    return Confirm.ask(f"[yellow]{msg}[/yellow]", default=default)
