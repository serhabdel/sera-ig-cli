"""The Feed panel — posts from the people you follow."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Static

from .. import api
from ..output import format_time
from .widgets import Avatar, RecordPanel

FEED_LIMIT = 20


class PostCard(Static):
    """One post in the feed."""

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
        caption = (record.get("caption") or "").replace("\n", " ")
        with Horizontal(classes="post-card"):
            yield Avatar(
                user.get("username"),
                enabled=self.show_avatar,
                client=self.client,
                user=user,
                classes="post-avatar")
            with VerticalScroll(classes="post-body"):
                yield Label(Text(f"@{user.get('username', '')}"), classes="post-author")
                if caption:
                    yield Label(Text(caption[:160]), classes="post-caption")
                yield Label(
                    Text(
                        f"♥ {record.get('like_count', 0)}   "
                        f"💬 {record.get('comment_count', 0)}   "
                        f"{format_time(record.get('taken_at'))}"
                    ),
                    classes="post-meta",
                )


class FeedPanel(RecordPanel):
    """The home timeline."""

    DEFAULT_CSS = """
    FeedPanel {
        layout: vertical;
    }
    .post-card {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
        border-bottom: solid $panel;
    }
    .post-avatar {
        width: 5;
        content-align: center middle;
    }
    .post-body {
        width: 1fr;
        height: auto;
    }
    .post-author {
        text-style: bold;
    }
    .post-caption, .post-meta {
        color: $text-muted;
    }
    """

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(client, **kwargs)
        self.posts: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        yield Static("", classes="record-panel-status")
        yield VerticalScroll(classes="record-list")

    def fetch_records(self) -> list[dict[str, Any]]:
        return api.timeline(self.client, amount=FEED_LIMIT)

    def row_for(self, record: dict[str, Any], index: int) -> Any:
        return PostCard(
            record,
            show_avatar=self.app.show_avatars,
            client=self.client,
            id=f"post-{index}")

    def empty_message(self) -> str:
        return "No posts in the feed"
