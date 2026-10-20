"""The story viewer.

Clicking somebody's story opens it here: the picture is drawn in the
terminal, and you move through somebody's stories with the arrow keys.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, Static

from .images import render_image, supports_images
from .worker import describe_error, run

#: How long a story stays on screen before it moves on.
STORY_SECONDS = 6


class StoryScreen(ModalScreen[None]):
    """Show one person's stories, one at a time."""

    DEFAULT_CSS = """
    StoryScreen {
        align: center middle;
    }
    #story-dialog {
        width: 70;
        max-width: 95%;
        height: 26;
        max-height: 90%;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    #story-title {
        height: 1;
        text-style: bold;
        color: $accent;
    }
    #story-image {
        height: 1fr;
        content-align: center middle;
    }
    #story-position {
        height: 1;
        color: $text-muted;
    }
    #story-hint {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, client: Any, record: dict[str, Any], **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.record = record
        self.stories = list(record.get("stories") or [])
        self.index = 0
        self._protocol = "halfblock"

    def compose(self) -> ComposeResult:
        with Vertical(id="story-dialog"):
            yield Label("", id="story-title")
            yield Static("", id="story-image")
            yield Label("", id="story-position")
            yield Label("← → to move  ·  Esc to close", id="story-hint")

    def on_mount(self) -> None:
        self._protocol = self.app.image_protocol
        self.show_story()
        self.set_interval(STORY_SECONDS, self.next)

    @property
    def current(self) -> dict[str, Any]:
        if not self.stories:
            return {}
        return self.stories[min(self.index, len(self.stories) - 1)]

    def show_story(self) -> None:
        """Draw the current story."""
        story = self.current
        if not story:
            self.dismiss(None)
            return

        user = self.record.get("user") or {}
        username = user.get("username") or "?"
        self.query_one("#story-title", Label).update(
            Text.assemble((f"@{username}", "bold"), (f"  ·  {story.get('kind', 'story')}", "dim"))
        )
        self.query_one("#story-position", Label).update(
            Text(f"{self.index + 1} of {len(self.stories)}")
        )

        image = self.query_one("#story-image", Static)
        url = story.get("thumbnail_url")
        if not url or not supports_images(self._protocol):
            image.update(Text("[no picture available for this terminal]", style="dim"))
            return

        def work() -> Any:
            response = self.client.private.get(url, timeout=30)
            response.raise_for_status()
            return response.content

        image.update(Text("Loading…", style="dim"))
        run(self.app, work, self._apply, self._failed, group="story", exclusive=True)

    def _apply(self, data: bytes) -> None:
        rendered = render_image(data, 40, self._protocol, height=18)
        if rendered is None:
            self.query_one("#story-image", Static).update(
                Text("[this terminal cannot draw images]", style="dim")
            )
            return
        self.query_one("#story-image", Static).update(rendered)

    def _failed(self, exc: BaseException) -> None:
        self.query_one("#story-image", Static).update(Text(describe_error(exc), style="dim"))

    def next(self) -> None:
        """Move to the next story, or close when there are none left."""
        if self.index + 1 < len(self.stories):
            self.index += 1
            self.show_story()
        else:
            self.dismiss(None)

    def previous(self) -> None:
        """Move back a story."""
        if self.index > 0:
            self.index -= 1
            self.show_story()

    def key_right(self) -> None:
        self.next()

    def key_left(self) -> None:
        self.previous()

    def key_escape(self) -> None:
        self.dismiss(None)
