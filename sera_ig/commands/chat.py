"""Direct-message commands.

These are the "one-turn" commands: each one does a single thing, prints the
result and exits — which makes them easy to use from a shell script or an
AI agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..errors import NotFoundError, UsageError
from ..models import message_to_dict, thread_to_dict
from ..output import console, emit, format_time, print_rows, print_table, truncate
from ..resolve import thread_title
from ..state import resolve_account, resolve_output

# ------------------------------------------------------------------ rendering


def _render_inbox(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No conversations.[/dim]")
        return
    rows = []
    for record in records:
        last = record.get("last_message") or {}
        preview = last.get("text") or f"[{last.get('kind', 'message')}]"
        rows.append(
            [
                record["id"],
                record["title"],
                truncate(preview, 48),
                format_time(record.get("last_activity_at")),
            ]
        )
    print_table(rows, ["id", "conversation", "last message", "activity"])


def _render_messages(target: Any, records: list[dict[str, Any]]) -> None:
    console.print(f"[bold magenta]{thread_title(target)}[/bold magenta]  [dim]{target.id}[/dim]")
    console.print()
    for record in records:
        who = "you" if record.get("is_sent_by_viewer") else "them"
        stamp = format_time(record.get("timestamp"))
        text = record.get("text") or ""
        media = record.get("media")
        if media:
            if media.get("url"):
                text = f"{text}\n[dim]{media['url']}[/dim]".strip()
            elif media.get("pk"):
                text = f"{text}\n[dim]post {media['pk']}[/dim]".strip()
            else:
                text = f"{text}\n[dim]media[/dim]".strip()
        if record.get("reactions"):
            emojis = "".join(r["emoji"] for r in record["reactions"])
            text = f"{text} {emojis}".strip()
        console.print(f"[dim]{stamp}[/dim] [cyan]{who}[/cyan]: {text}")
        console.print()


# ------------------------------------------------------------------- commands


def inbox(
    limit: int = typer.Option(20, "--limit", "-n", help="How many conversations to show"),
    thread_filter: str = typer.Option(
        None, "--filter", help="Filter conversations: unread, flagged or all"
    ),
    search: str = typer.Option(None, "--search", "-s", help="Filter by name or username"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """List your direct-message conversations."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.list_threads(
            client,
            amount=limit,
            selected_filter=thread_filter,
            search=search,
            message_limit=1,
        )
    emit(fmt, records, lambda: _render_inbox(records))


def read(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many messages to show"),
    mark_seen: bool = typer.Option(False, "--mark-seen", help="Mark the thread as read"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Read the messages of a conversation."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        records = api.read_messages(client, target, limit=limit)
        if mark_seen:
            api.mark_seen(client, target)
    payload = {"thread": thread_to_dict(target), "messages": records}
    emit(fmt, payload, lambda: _render_messages(target, records))


def send(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    text: str = typer.Option(None, "--text", "-t", help="The message to send"),
    media: Path = typer.Option(
        None, "--media", "-m", help="Path to a photo or video to send"
    ),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Send a message to a conversation."""
    fmt = resolve_output(output)
    if not text and media is None:
        raise UsageError("Provide --text, --media, or both.")

    records: list[dict[str, Any]] = []
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread, create=bool(text))
        if media is not None:
            records.append(api.send_media(client, target, media))
        if text:
            records.append(api.send_text(client, target, text))

    payload = records[0] if len(records) == 1 else {"sent": records}
    emit(fmt, payload, lambda: console.print("[green]Message sent.[/green]"))


def reply(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    message_id: str = typer.Option(..., "--message-id", "-i", help="Id of the message to reply to"),
    text: str = typer.Option(..., "--text", "-t", help="The reply"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Reply to a specific message."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        record = api.send_text(client, target, text, reply_to={"id": message_id})
    emit(fmt, record, lambda: console.print("[green]Reply sent.[/green]"))


def react(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    message_id: str = typer.Option(..., "--message-id", "-i", help="Id of the message"),
    emoji: str = typer.Option("❤", "--emoji", "-e", help="Emoji to react with"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """React to a message with an emoji."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        api.react(client, target, message_id, emoji)
    payload = {"thread_id": str(target.id), "message_id": message_id, "emoji": emoji}
    emit(fmt, payload, lambda: console.print(f"[green]Reacted with {emoji}[/green]"))


def unsend(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    message_id: str = typer.Option(..., "--message-id", "-i", help="Id of the message"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Unsend (delete) a message you sent."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        api.unsend(client, target, message_id)
    payload = {"thread_id": str(target.id), "message_id": message_id, "unsent": True}
    emit(fmt, payload, lambda: console.print("[green]Message unsent.[/green]"))


def seen(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Mark a conversation as read."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        api.mark_seen(client, target)
    payload = {"thread_id": str(target.id), "seen": True}
    emit(fmt, payload, lambda: console.print("[green]Marked as read.[/green]"))


def search(
    query: str = typer.Argument(..., help="Name or username to search for"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Search Instagram for people."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.search_users(client, query)
    emit(
        fmt,
        records,
        lambda: print_rows(records, ["username", "full_name", "pk"])
        if records
        else console.print("[dim]No users found.[/dim]"),
    )


def download(
    thread: str = typer.Argument(..., help="Thread id, username or conversation title"),
    message_id: str = typer.Option(..., "--message-id", "-i", help="Id of the message"),
    destination: Path = typer.Option(
        None, "--output-path", "-d", help="Where to save the file (file or directory)"
    ),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Download the media attached to a message."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        target = api.get_thread(client, thread)
        message = client.direct_message(int(target.id), int(message_id), amount=1)
        record = message_to_dict(message)
        url = record.get("media_url")
        if not url:
            raise NotFoundError("That message has no downloadable media.")
        response = client.private.get(url, timeout=60)
        response.raise_for_status()

    target_path = destination or (Path.cwd() / f"{message_id}.jpg")
    target_path = target_path.expanduser()
    if target_path.is_dir():
        target_path = target_path / f"{message_id}.jpg"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(response.content)

    payload = {"path": str(target_path), "bytes": target_path.stat().st_size}
    emit(fmt, payload, lambda: console.print(f"[green]Saved to {target_path}[/green]"))
