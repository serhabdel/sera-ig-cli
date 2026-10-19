"""User commands — ``seraig user``, ``seraig posts``, ``seraig followers`` …"""

from __future__ import annotations

from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..output import console, emit, format_time, print_rows, print_table, truncate
from ..state import resolve_account, resolve_output


def _render_profile(record: dict[str, Any]) -> None:
    from rich.panel import Panel

    verified = " ✓" if record.get("is_verified") else ""
    private = " [dim](private)[/dim]" if record.get("is_private") else ""
    body = (
        f"[bold]{record.get('full_name') or record.get('username')}[/bold]{verified}{private}\n"
        f"@{record.get('username')}\n\n"
        f"{record.get('posts', 0)} posts   {record.get('followers', 0)} followers   "
        f"{record.get('following', 0)} following\n\n"
        f"{record.get('biography') or ''}\n"
    )
    if record.get("external_url"):
        body += f"\n[blue]{record['external_url']}[/blue]"
    console.print(Panel(body, title="PROFILE", border_style="magenta"))


def _render_posts(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No posts.[/dim]")
        return
    rows = []
    for record in records:
        rows.append(
            [
                record.get("code"),
                record.get("kind"),
                truncate(record.get("caption", ""), 50),
                record.get("like_count"),
                record.get("comment_count"),
                format_time(record.get("taken_at")),
            ]
        )
    print_table(rows, ["code", "kind", "caption", "likes", "comments", "posted"])


def _render_users(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No accounts.[/dim]")
        return
    print_rows(records, ["username", "full_name", "pk"])


def user(
    username: str = typer.Argument(..., help="Username to look up"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show a profile summary."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        record = api.user_profile(client, username.lstrip("@"))
    emit(fmt, record, lambda: _render_profile(record))


def posts(
    username: str = typer.Argument(..., help="Username whose posts to show"),
    limit: int = typer.Option(12, "--limit", "-n", help="How many posts to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show the latest posts of an account."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.user_posts(client, username.lstrip("@"), amount=limit)
    emit(fmt, records, lambda: _render_posts(records))


def followers(
    username: str = typer.Argument(..., help="Username whose followers to show"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many followers to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show the followers of an account."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.user_followers(client, username.lstrip("@"), amount=limit)
    emit(fmt, records, lambda: _render_users(records))


def following(
    username: str = typer.Argument(..., help="Username whose followings to show"),
    limit: int = typer.Option(20, "--limit", "-n", help="How many accounts to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show the accounts an account follows."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.user_following(client, username.lstrip("@"), amount=limit)
    emit(fmt, records, lambda: _render_users(records))
