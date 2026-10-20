"""The message search overlay.

Instagram can search every message you have ever received, not just the
conversations in your inbox. This is that search, in an overlay.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList

from .. import api
from ..output import relative_time
from .worker import describe_error, run


class SearchScreen(ModalScreen[str | None]):
    """Search every conversation for a piece of text."""

    DEFAULT_CSS = """
    SearchScreen {
        align: center middle;
    }
    #search-dialog {
        width: 80;
        max-width: 90%;
        height: 24;
        max-height: 80%;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    .search-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #search-results {
        height: 1fr;
        margin-top: 1;
    }
    #search-status {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.results: list[dict[str, Any]] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="search-dialog"):
            yield Label("Search every message", classes="search-title")
            yield Input(placeholder="Type what you are looking for", id="search-input")
            yield OptionList(id="search-results")
            yield Label("Esc to close", id="search-status")

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        query = event.value.strip()
        self.set_status("Type something to search" if not query else "Searching…")
        if not query:
            self.show_results([])
            return
        run(
            self.app,
            lambda: api.search_messages(self.client, query),
            self.show_results,
            self._failed,
            group="search",
            exclusive=True,
        )

    def show_results(self, results: list[dict[str, Any]]) -> None:
        """Show the messages that matched."""
        self.results = results or []
        listing = self.query_one("#search-results", OptionList)
        listing.clear_options()
        for record in self.results:
            conversation = record.get("conversation") or {}
            title = conversation.get("title") or "conversation"
            snippet = (record.get("text") or "[media]").replace("\n", " ")
            when = relative_time(record.get("timestamp"))
            listing.add_option(
                Text.assemble(
                    (f"{title}", "bold"),
                    ("  ·  ", "dim"),
                    (snippet[:60], ""),
                    (f"  {when}", "dim"),
                )
            )
        if not self.results:
            self.set_status("Nothing found")
        else:
            self.set_status(f"{len(self.results)} message(s) — enter to open the conversation")

    def _failed(self, exc: BaseException) -> None:
        self.set_status(describe_error(exc))

    def set_status(self, text: str) -> None:
        self.query_one("#search-status", Label).update(Text(text, style="dim"))

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """Open the conversation the selected message belongs to."""
        index = event.option_index
        if index is None or index >= len(self.results):
            return
        conversation = self.results[index].get("conversation") or {}
        self.dismiss(str(conversation.get("id") or ""))
