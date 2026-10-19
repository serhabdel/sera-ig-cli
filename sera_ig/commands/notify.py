"""Notification commands — ``seraig notify``."""

from __future__ import annotations

from typing import Any

import typer

from .. import api
from .. import client as client_module
from ..output import console, emit, print_table, truncate
from ..state import resolve_account, resolve_output


def _render(records: list[dict[str, Any]]) -> None:
    if not records:
        console.print("[dim]No recent activity.[/dim]")
        return
    rows = []
    for record in records:
        user = record.get("user") or {}
        rows.append(
            [
                record.get("type"),
                f"@{user.get('username')}" if user.get("username") else "",
                truncate(record.get("text", ""), 60),
                (record.get("media") or {}).get("code", ""),
            ]
        )
    print_table(rows, ["type", "user", "activity", "post"])


def notify(
    limit: int = typer.Option(20, "--limit", "-n", help="How many notifications to show"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show recent activity — likes, comments, follows and mentions."""
    fmt = resolve_output(output)
    with client_module.connect(resolve_account(account)) as client:
        records = api.notifications(client, limit=limit)
    emit(fmt, records, lambda: _render(records))
