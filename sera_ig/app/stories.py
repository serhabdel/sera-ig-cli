"""The Stories panel — the people you follow who have active stories."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Static

from .. import api
from ..output import format_time
from .widgets import Avatar, Clickable, RecordPanel

STORY_LIMIT = 20


class StoryCard(Clickable):
    """One user's stories. Clicking it opens the viewer."""

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
        stories = record.get("stories") or []
        first = stories[0] if stories else {}
        with Horizontal(classes="story-card"):
            yield Avatar(
                user.get("username"),
                enabled=self.show_avatar,
                client=self.client,
                user=user,
                classes="story-avatar")
            with VerticalScroll(classes="story-body"):
                yield Label(Text(f"@{user.get('username', '')}"), classes="story-author")
                yield Label(
                    Text(f"{record.get('story_count', 0)} stories"),
                    classes="story-count",
                )
                if first:
                    yield Label(Text(format_time(first.get("taken_at"))), classes="story-time")


class StoriesPanel(RecordPanel):
    """The stories tray."""

    DEFAULT_CSS = """
    StoriesPanel {
        layout: vertical;
    }
    .story-card {
        height: auto;
        padding: 0 1;
        margin: 0 0 1 0;
        border-bottom: solid $panel;
    }
    .story-avatar {
        width: 5;
        height: 100%;
        content-align: left top;
    }
    StoryCard {
        height: auto;
    }
    .story-card {
        height: auto;
    }
    .story-body {
        width: 1fr;
        height: auto;
    }
    .story-author {
        text-style: bold;
    }
    .story-count, .story-time {
        color: $text-muted;
    }
    """

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(client, **kwargs)
        self.tray: list[dict[str, Any]] = []
        self._keys: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static("", classes="record-panel-status")
        yield VerticalScroll(classes="record-list")

    def fetch_records(self) -> list[dict[str, Any]]:
        """The stories of the people you have conversations with.

        The tray endpoint is asked first; when it comes back empty, the
        people in your inbox are asked directly.
        """
        keys: list[str] = []
        records = api.stories_tray(self.client, keys=keys)
        if not records:
            records = api.stories_tray(
                self.client, api.conversation_user_ids(self.client), keys=keys
            )
        self._keys = keys
        return records

    def row_for(self, record: dict[str, Any], index: int) -> Any:
        return StoryCard(
            record,
            show_avatar=self.app.show_avatars,
            client=self.client,
            id=f"story-{index}")

    def empty_message(self) -> str:
        if self._keys:
            return f"No active stories (Instagram answered: {', '.join(self._keys)})"
        return "No active stories right now"
