"""Story commands — ``seraig stories``."""

from __future__ import annotations

from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..output import console, emit, format_time, print_table
from ..state import resolve_account, resolve_output


def _render_tray(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No active stories.[/dim]")
        return
    rows = []
    for record in records:
        user = record.get("user") or {}
        first = (record.get("stories") or [{}])[0]
        rows.append(
            [
                f"@{user.get('username')}",
                user.get("full_name", ""),
                record.get("story_count"),
                format_time(first.get("taken_at")),
            ]
        )
    print_table(rows, ["user", "name", "stories", "latest"])


def _render_user_stories(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No active stories for that account.[/dim]")
        return
    rows = []
    for record in records:
        rows.append(
            [
                record.get("pk"),
                record.get("kind"),
                format_time(record.get("taken_at")),
                record.get("thumbnail_url") or record.get("video_url") or "",
            ]
        )
    print_table(rows, ["id", "kind", "posted", "url"])


def stories(
    username: str = typer.Argument(None, help="Show the stories of one account"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
    debug: bool = typer.Option(
        False, "--debug", help="Also show what Instagram answered for the stories tray"
    ),
) -> None:
    """Show the stories of the people you follow, or of one account."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        if username:
            records = api.user_stories(client, username.lstrip("@"))
            emit(fmt, records, lambda: _render_user_stories(records))
        else:
            tray = api.stories_tray(client) or api.stories_tray(
                client, api.conversation_user_ids(client)
            )
            emit(fmt, tray, lambda: _render_tray(tray))
            if debug:
                console.print(
                    f"[dim]tray response keys: {', '.join(api.stories_raw_keys(client))}[/dim]"
                )
