"""
AI Engine CLI — chat command.

    # Interactive REPL (default)
    ai-engine chat --agent my-agent

    # Single-shot message
    ai-engine chat --agent my-agent --once "What is the capital of France?"

    # Pipe-friendly (--once reads from stdin when no MESSAGE given)
    echo "Explain async/await" | ai-engine chat --agent my-agent --once
"""

from __future__ import annotations

import sys
from typing import Annotated, Optional

try:
    import typer
except ImportError as e:  # pragma: no cover
    raise ImportError("Install with: pip install ai-engine[cli]") from e

from ai_engine.adapters.cli.console import (
    chat_print_response,
    chat_user_prompt,
    console,
    err_console,
    print_header,
    print_info,
    print_warning,
)
from ai_engine.adapters.cli.utils import (
    DEFAULT_DB,
    abort,
    get_storage,
    resolve_agent,
)

app = typer.Typer(
    name="chat",
    help="Chat with an agent (interactive REPL or single-shot).",
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def chat(
    ctx: typer.Context,
    agent: Annotated[
        str,
        typer.Option(
            "--agent", "-a", help="Agent ID, slug, or prefix", envvar="AI_ENGINE_AGENT"
        ),
    ],
    once: Annotated[
        bool,
        typer.Option(
            "--once/--interactive", "-1", help="Send a single message then exit"
        ),
    ] = False,
    message: Annotated[
        Optional[str],
        typer.Argument(help="Message to send (--once mode; reads stdin if omitted)"),
    ] = None,
    conversation_id: Annotated[
        Optional[str],
        typer.Option("--conversation", "-c", help="Resume an existing conversation"),
    ] = None,
    db: Annotated[str, typer.Option("--db", envvar="AI_ENGINE_DB")] = DEFAULT_DB,
    show_model: Annotated[
        bool,
        typer.Option(
            "--show-model/--no-show-model", help="Show model name in responses"
        ),
    ] = True,
) -> None:
    """Chat with an agent in interactive mode or send a single message."""
    # Don't run if a sub-command is being invoked
    if ctx.invoked_subcommand is not None:
        return

    storage = get_storage(db)
    ag = resolve_agent(storage, agent)
    provider = storage.get_provider(ag.provider_id)
    model_name = provider.default_model if (provider and show_model) else None

    from ai_engine.services.agent import AgentService

    svc = AgentService(storage)

    # ── Single-shot mode ─────────────────────────────────────────────────────
    if once:
        # Accept message from positional arg or stdin
        if message is None:
            if sys.stdin.isatty():
                abort("--once requires a MESSAGE argument or piped stdin.")
            message = sys.stdin.read().strip()
        if not message:
            abort("Message cannot be empty.")

        try:
            response, conv = svc.chat(
                ag.id,
                message,
                conversation_id=conversation_id,
            )
        except Exception as e:
            abort(f"Chat failed: {e}")
            return  # unreachable — abort raises

        chat_print_response(response.content, model_name)
        print_info(f"Conversation ID: {conv.id}")
        return

    # ── Interactive REPL mode ────────────────────────────────────────────────
    print_header(
        f"Chat with {ag.name}",
        subtitle=f"Model: {model_name or '—'}  |  Type 'exit' or Ctrl-C to quit.",
    )
    if conversation_id:
        print_info(f"Resuming conversation {conversation_id[:8]}…")

    conv_id = conversation_id

    while True:
        try:
            user_input = chat_user_prompt(ag.name)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Bye![/dim]")
            raise typer.Exit(0)

        if user_input.strip().lower() in {"exit", "quit", "bye", "/exit", "/quit"}:
            console.print("[dim]Bye![/dim]")
            raise typer.Exit(0)

        if not user_input.strip():
            continue

        # Show a subtle spinner while waiting
        try:
            with console.status("[dim]Thinking…[/dim]", spinner="dots"):
                response, conv_obj = svc.chat(
                    ag.id,
                    user_input,
                    conversation_id=conv_id,
                )
            conv_id = conv_obj.id  # keep conversation across turns
        except KeyboardInterrupt:
            print_warning("Interrupted.")
            continue
        except Exception as e:
            err_console.print(f"[red]Error: {e}[/red]")
            continue

        chat_print_response(response.content, model_name)
