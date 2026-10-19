"""Feed commands — ``seraig feed``, ``seraig reels``."""

from __future__ import annotations

from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..output import console, emit, format_time, print_table, truncate
from ..state import resolve_account, resolve_output


def _render_media(records: list[dict[str, Any]], title: str) -> None:
    if not records:
        console.print("[dim]Nothing here.[/dim]")
        return
    rows = []
    for record in records:
        rows.append(
            [
                record.get("code"),
                f"@{record['user']['username']}" if record.get("user") else "",
                record.get("kind"),
                truncate(record.get("caption", ""), 50),
                record.get("like_count"),
                record.get("comment_count"),
                format_time(record.get("taken_at")),
            ]
        )
    print_table(rows, ["code", "author", "kind", "caption", "likes", "comments", "posted"])


def feed(
    limit: int = typer.Option(20, "--limit", "-n", help="How many posts to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show posts from the people you follow."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.timeline(client, amount=limit)
    emit(fmt, records, lambda: _render_media(records, "Feed"))


def reels(
    explore: bool = typer.Option(False, "--explore", help="Show explore reels instead"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many reels to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show reels."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.explore_reels(client, amount=limit) if explore else api.reels(client, amount=limit)
    emit(fmt, records, lambda: _render_media(records, "Reels"))
