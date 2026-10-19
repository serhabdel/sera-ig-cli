"""Media commands — ``seraig like``, ``seraig comment``, ``seraig download`` …"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..output import console, emit, format_time, print_table, truncate
from ..state import resolve_account, resolve_output


def _render_media(record: dict[str, Any]) -> None:
    user = record.get("user") or {}
    console.print(f"[bold]@{user.get('username', '')}[/bold]  [dim]{record.get('kind')}[/dim]")
    if record.get("caption"):
        console.print(record["caption"])
    console.print()
    console.print(
        f"[red]♥[/red] {record.get('like_count', 0)} likes   "
        f"{record.get('comment_count', 0)} comments   "
        f"{format_time(record.get('taken_at'))}"
    )
    console.print(f"[blue]{record.get('url')}[/blue]")


def _render_comments(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No comments.[/dim]")
        return
    rows = []
    for record in records:
        user = record.get("user") or {}
        rows.append(
            [
                f"@{user.get('username', '')}",
                truncate(record.get("text", ""), 70),
                record.get("like_count"),
                format_time(record.get("created_at")),
            ]
        )
    print_table(rows, ["user", "comment", "likes", "posted"])


def info(
    media: str = typer.Argument(..., help="Media id, short code or post URL"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show the details of a post."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        record = api.media_info(client, media)
    emit(fmt, record, lambda: _render_media(record))


def like(
    media: str = typer.Argument(..., help="Media id, short code or post URL"),
    unlike: bool = typer.Option(False, "--unlike", help="Remove the like instead"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Like a post."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        api.like_media(client, media, revert=unlike)
    payload = {"media": media, "liked": not unlike}
    emit(fmt, payload, lambda: console.print("[green]Liked.[/green]" if not unlike else "[green]Like removed.[/green]"))


def comment(
    media: str = typer.Argument(..., help="Media id, short code or post URL"),
    text: str = typer.Option(..., "--text", "-t", help="The comment"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Comment on a post."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        record = api.comment_media(client, media, text)
    emit(fmt, record, lambda: console.print("[green]Comment posted.[/green]"))


def comments(
    media: str = typer.Argument(..., help="Media id, short code or post URL"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many comments to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """List the comments of a post."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.media_comments(client, media, amount=limit)
    emit(fmt, records, lambda: _render_comments(records))


def download(
    media: str = typer.Argument(..., help="Media id, short code or post URL"),
    destination: Path = typer.Option(
        None, "-d", "--output-path", help="Where to save it (file or directory)"
    ),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Download a photo or video."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        path = api.download_media(client, media, destination)
    payload = {"path": str(path), "bytes": path.stat().st_size if path.exists() else 0}
    emit(fmt, payload, lambda: console.print(f"[green]Saved to {path}[/green]"))
