"""Shared widgets for the application."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from ..output import relative_time
from .images import avatar_text
from .worker import PanelBase


class Avatar(Static):
    """A coloured initial-letter avatar.

    It never waits on the network: the colour comes from a hash of the
    username, so a list of a hundred conversations renders instantly. When
    ``ui.avatar_images`` is on, the real picture is fetched in the background
    and replaces the letter once it arrives.
    """

    DEFAULT_CSS = """
    Avatar {
        width: 5;
        height: 100%;
        content-align: left top;
    }
    """

    def __init__(
        self,
        username: str | None = None,
        *,
        enabled: bool = True,
        client: Any = None,
        user: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(avatar_text(username, enabled), **kwargs)
        self.username = username
        self.avatar_enabled = enabled
        self.client = client
        self.user = user or {}

    def on_mount(self) -> None:
        if self.client and self.user.get("profile_pic_url"):
            self._load_picture()

    def _load_picture(self) -> None:
        from .images import fetch_avatar
        from .worker import run

        def work() -> Any:
            return fetch_avatar(self.client, self.user)

        run(self.app, work, self._apply_picture, lambda _exc: None, group="avatars", exclusive=False)

    def _apply_picture(self, path: Any) -> None:
        if path is None:
            return
        from .images import render_avatar_image

        rendered = render_avatar_image(path, size=2)
        if rendered is not None:
            self.update(rendered)

    def set_username(self, username: str | None) -> None:
        """Point the avatar at another user."""
        self.username = username
        self.update(avatar_text(username, self.avatar_enabled))

    def set_enabled(self, enabled: bool) -> None:
        """Show or hide the avatar."""
        self.avatar_enabled = enabled
        self.update(avatar_text(self.username, enabled))


class Clickable(Static):
    """A static block that reports clicks and double clicks.

    Textual sends the click to the widget under the pointer, so the simplest
    way to make a rich, multi-line row clickable is to wrap it in one of
    these.
    """

    class Pressed(Message):
        """Posted when the widget is clicked."""

        def __init__(self, widget: Clickable) -> None:
            super().__init__()
            self.widget = widget

        @property
        def control(self) -> Clickable:
            """The widget that was pressed."""
            return self.widget

    class DoublePressed(Message):
        """Posted when the widget is double clicked."""

        def __init__(self, widget: Clickable) -> None:
            super().__init__()
            self.widget = widget

        @property
        def control(self) -> Clickable:
            """The widget that was pressed."""
            return self.widget

    def on_click(self, event: Any) -> None:
        self.post_message(self.Pressed(self))

    def on_double_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.DoublePressed(self))


class AvatarRow(Horizontal):
    """An avatar next to a block of text."""

    def __init__(self, username: str | None, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.username = username

    def compose(self) -> ComposeResult:
        yield Avatar(self.username)
        yield from super().compose()


def line_summary(record: dict[str, Any], *, width: int = 48) -> str:
    """Return the preview text of a conversation."""
    last = record.get("last_message") or {}
    text = last.get("text") or ""
    if not text:
        kind = last.get("kind") or "message"
        text = f"[{kind}]"
    return text.replace("\n", " ")[:width]


def activity_label(record: dict[str, Any]) -> str:
    """Return the relative time of a conversation."""
    return relative_time(record.get("last_activity_at"))


def styled_name(username: str | None, *, bold: bool = True) -> Text:
    """Return a username in the interface's accent colour."""
    style = "bold" if bold else ""
    return Text(username or "?", style=style)


class RecordPanel(PanelBase):
    """A panel that shows a list of records fetched in the background.

    Feed, stories and notifications all follow the same shape: fetch a list,
    render it, show a loading state while it is on its way, and keep the
    previous data when a refresh fails.
    """

    DEFAULT_CSS = """
    RecordPanel {
        layout: vertical;
    }
    .record-panel-status {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    .record-panel-status.error {
        color: $error;
    }
    .record-list {
        height: 1fr;
    }
    """

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.records: list[dict[str, Any]] = []

    # ------------------------------------------------------------- to fill
    def fetch_records(self) -> list[dict[str, Any]]:
        """Return the records to show — implemented by each panel."""
        raise NotImplementedError

    def row_for(self, record: dict[str, Any], index: int) -> Any:
        """Return the widget shown for *record*."""
        raise NotImplementedError

    def empty_message(self) -> str:
        """What to show when there is nothing to list."""
        return "Nothing here"

    # -------------------------------------------------------------- data
    def load(self) -> None:
        """Fetch the records in the background."""
        self.set_status("Loading…")
        self.fetch(self.fetch_records, self.apply_records)

    def apply_records(self, records: list[dict[str, Any]]) -> None:
        """Show the fetched records."""
        self.records = records or []
        listing = self.query_one(".record-list")
        listing.remove_children()
        for index, record in enumerate(self.records):
            listing.mount(self.row_for(record, index))
        self.set_status("" if self.records else self.empty_message())

    def reload(self) -> None:
        """Reload the records."""
        self.load()

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show a line of status."""
        status = self.query_one(".record-panel-status")
        status.update(Text(text))
        status.set_class(error, "error")

    def fail(self, exc: BaseException) -> None:
        """Report a failed refresh, keeping whatever is already on screen."""
        from .worker import describe_error

        self.set_status(describe_error(exc), error=True)
        self.app.report_error(exc)
