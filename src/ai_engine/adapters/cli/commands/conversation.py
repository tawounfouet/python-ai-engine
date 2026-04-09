"""
AI Engine CLI — conversation commands.

    ai-engine conversation list [--agent <id>]
    ai-engine conversation show <id>
    ai-engine conversation history <id> [--limit N]
    ai-engine conversation delete <id>
"""

from __future__ import annotations

from typing import Annotated, Optional

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError("Install with: pip install ai-engine[cli]") from e

from ai_engine.adapters.cli.console import (
    confirm,
    console,
    print_conversations_table,
    print_header,
    print_messages,
    print_success,
)
from ai_engine.adapters.cli.utils import (
    DEFAULT_DB,
    get_storage,
    resolve_agent,
    resolve_conversation,
)

app = typer.Typer(
    name="conversation",
    help="Manage conversations.",
    no_args_is_help=True,
)


@app.command("list")
def conversation_list(
    agent: Annotated[
        Optional[str], typer.Option("--agent", "-a", help="Filter by agent ID or slug")
    ] = None,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """List conversations, optionally filtered by agent."""
    storage = get_storage(db)
    agent_id: str | None = None
    if agent:
        a = resolve_agent(storage, agent)
        agent_id = a.id
    conversations = storage.list_conversations(agent_id=agent_id)
    print_conversations_table(conversations)


@app.command("show")
def conversation_show(
    identifier: Annotated[str, typer.Argument(help="Conversation ID or prefix")],
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Show conversation details and full message history."""
    storage = get_storage(db)
    conv = resolve_conversation(storage, identifier)

    print_header(
        f"Conversation: {conv.title or '(no title)'}",
        subtitle=f"ID: {conv.id}  |  Status: {conv.status}",
    )

    messages = storage.get_messages(conv.id)
    print_messages(messages, show_meta=True)


@app.command("history")
def conversation_history(
    identifier: Annotated[str, typer.Argument(help="Conversation ID or prefix")],
    limit: Annotated[
        Optional[int], typer.Option("--limit", "-l", help="Last N messages")
    ] = None,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Print the message history of a conversation."""
    storage = get_storage(db)
    conv = resolve_conversation(storage, identifier)
    messages = storage.get_messages(conv.id, limit=limit)
    title = conv.title or conv.id[:8]
    console.print(
        f"\n[dim]Showing {len(messages)} message(s) for '[bold]{title}[/bold]'[/dim]\n"
    )
    print_messages(messages, show_meta=True)


@app.command("delete")
def conversation_delete(
    identifier: Annotated[str, typer.Argument(help="Conversation ID or prefix")],
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Skip confirmation")] = False,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
) -> None:
    """Delete a conversation and all its messages."""
    storage = get_storage(db)
    conv = resolve_conversation(storage, identifier)
    title = conv.title or conv.id[:8]
    if not yes and not confirm(f"Delete conversation '{title}' and all its messages?"):
        raise typer.Abort()
    storage.delete_conversation(conv.id)
    print_success(f"Conversation '{title}' deleted.")
