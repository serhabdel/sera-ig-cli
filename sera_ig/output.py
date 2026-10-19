"""Output helpers.

Every command produces two shapes of the same data: a human-readable one
(default) and a machine-readable JSON one (``-o json``). The JSON shape is
what AI agents and scripts consume, so it is kept stable and flat.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime, timezone
from typing import Any

from rich.console import Console
from rich.table import Table
from rich.text import Text

TEXT = "text"
JSON = "json"
FORMATS = (TEXT, JSON)

console = Console()
err_console = Console(stderr=True)


def resolve_format(explicit: str | None, default: str = TEXT) -> str:
    """Normalise and validate an output format."""
    value = (explicit or default).strip().lower()
    if value not in FORMATS:
        raise ValueError(f"Unknown output format '{value}'. Use one of: {', '.join(FORMATS)}")
    return value


def dump_json(data: Any) -> None:
    """Print *data* as JSON on stdout."""
    sys.stdout.write(json.dumps(data, indent=2, default=_json_default, ensure_ascii=False))
    sys.stdout.write("\n")


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, (set, frozenset)):
        return sorted(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return str(value)


def emit(fmt: str, data: Any, render: Callable[[], None]) -> None:
    """Print *data* as JSON, or run the *render* callback for text output."""
    if fmt == JSON:
        dump_json(data)
    else:
        render()


def print_table(
    rows: Sequence[Sequence[Any]],
    headers: Sequence[str],
    *,
    title: str | None = None,
    caption: str | None = None,
) -> None:
    """Render a simple table."""
    table = Table(title=title, caption=caption, header_style="bold magenta", show_lines=False)
    for header in headers:
        table.add_column(header, overflow="fold")
    for row in rows:
        table.add_row(*["" if cell is None else str(cell) for cell in row])
    console.print(table)


def print_rows(records: Iterable[dict[str, Any]], columns: Sequence[str]) -> None:
    """Render a list of dicts as a table using *columns* as the key order."""
    headers = list(columns)
    table = Table(header_style="bold magenta", show_lines=False)
    for header in headers:
        table.add_column(header, overflow="fold")
    for record in records:
        table.add_row(*["" if record.get(key) is None else str(record.get(key)) for key in headers])
    console.print(table)


def truncate(text: str, width: int) -> str:
    """Shorten *text* to *width* characters, adding an ellipsis."""
    text = (text or "").replace("\n", " ")
    if len(text) <= width:
        return text
    if width <= 1:
        return text[:width]
    return text[: width - 1] + "…"


def _as_datetime(value: Any) -> datetime | None:
    """Coerce a datetime or an ISO string into a datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    return None


def format_time(value: datetime | str | None) -> str:
    """Render a timestamp as a compact local time string."""
    moment = _as_datetime(value)
    if moment is None:
        return ""
    return moment.astimezone().strftime("%Y-%m-%d %H:%M")


def relative_time(value: datetime | str | None) -> str:
    """Render a timestamp as ``3m``, ``2h``, ``5d`` …"""
    moment = _as_datetime(value)
    if moment is None:
        return ""
    delta = datetime.now(timezone.utc) - moment.astimezone(timezone.utc)
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "now"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    if seconds < 86400 * 30:
        return f"{seconds // 86400}d"
    return moment.astimezone().strftime("%Y-%m-%d")


def media_kind(media_type: int | None, product_type: str | None = None) -> str:
    """Human label for an Instagram media type."""
    product = (product_type or "").lower()
    if product == "igtv":
        return "igtv"
    if product == "clips":
        return "reel"
    return {1: "photo", 2: "video", 8: "album"}.get(media_type or 0, "media")


def status_marker(ok: bool, yes: str = "✓", no: str = "✗") -> Text:
    """A coloured yes/no marker."""
    return Text(yes if ok else no, style="green" if ok else "red")


def ok(message: str) -> None:
    """Print a success line."""
    console.print(f"[green]✓[/green] {message}")


def warn(message: str) -> None:
    """Print a warning line on stderr."""
    err_console.print(f"[yellow]![/yellow] {message}")


def fail(message: str) -> None:
    """Print an error line on stderr."""
    err_console.print(f"[red]✗[/red] {message}")
