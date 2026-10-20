"""The Notifications panel — likes, comments, follows and mentions."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Static

from .. import api
from ..output import relative_time
from .widgets import Avatar, RecordPanel

NOTIFY_LIMIT = 30


class ActivityRow(Static):
    """One activity entry."""

    def __init__(
        self,
        record: dict[str, Any],
        *,
        show_avatar: bool = True,
        client: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.record = record
        self.show_avatar = show_avatar
        self.client = client

    def compose(self) -> ComposeResult:
        record = self.record
        user = record.get("user") or {}
        when = relative_time(record.get("timestamp"))
        with Horizontal(classes="activity-row"):
            yield Avatar(
                user.get("username"),
                enabled=self.show_avatar,
                client=self.client,
                user=user,
                classes="activity-avatar")
            with VerticalScroll(classes="activity-body"):
                yield Label(
                    Text(
                        f"{user.get('username') or 'someone'} "
                        f"{record.get('text') or record.get('type', 'acted')}"
                    ),
                    classes="activity-text",
                )
                yield Label(Text(when), classes="activity-time")


class NotifyPanel(RecordPanel):
    """The activity feed."""

    DEFAULT_CSS = """
    NotifyPanel {
        layout: vertical;
    }
    .activity-row {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
    }
    .activity-avatar {
        width: 5;
        content-align: center middle;
    }
    .activity-body {
        width: 1fr;
        height: auto;
    }
    .activity-time {
        color: $text-muted;
    }
    """

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(client, **kwargs)
        self.activities: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("", classes="record-panel-status")
        yield VerticalScroll(classes="record-list")

    def fetch_records(self) -> list[dict[str, Any]]:
        return api.notifications(self.client, limit=NOTIFY_LIMIT)

    def row_for(self, record: dict[str, Any], index: int) -> Any:
        return ActivityRow(
            record,
            show_avatar=self.app.show_avatars,
            client=self.client,
            id=f"activity-{index}")

    def empty_message(self) -> str:
        return "No recent activity"
