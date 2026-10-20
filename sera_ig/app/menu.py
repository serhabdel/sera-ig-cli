"""A small action menu.

Right-clicking a conversation or a message opens this: a list of things that
can be done with it.
"""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Label, OptionList


class ActionMenu(ModalScreen[str | None]):
    """Ask the user to pick one of a few actions."""

    DEFAULT_CSS = """
    ActionMenu {
        align: center middle;
    }
    #menu-dialog {
        width: 46;
        max-width: 90%;
        height: auto;
        max-height: 80%;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    .menu-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #menu-hint {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, actions: list[tuple[str, str, str]], **kwargs: Any) -> None:
        """*actions* is a list of ``(key, label, help)``."""
        super().__init__(**kwargs)
        self.title_text = title
        self.actions = actions

    def compose(self) -> ComposeResult:
        with Vertical(id="menu-dialog"):
            yield Label(self.title_text, classes="menu-title")
            yield OptionList(
                *(Text(label) for _, label, _ in self.actions), id="menu-options"
            )
            yield Label("Esc to close", id="menu-hint")

    def on_mount(self) -> None:
        self.query_one("#menu-options", OptionList).focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        index = event.option_index
        if index is None or index >= len(self.actions):
            return
        self.dismiss(self.actions[index][0])

    def key_escape(self) -> None:
        self.dismiss(None)


class PromptScreen(ModalScreen[str | None]):
    """Ask for one line of text."""

    DEFAULT_CSS = """
    PromptScreen {
        align: center middle;
    }
    #prompt-dialog {
        width: 56;
        max-width: 90%;
        height: auto;
        background: $surface;
        border: round $primary;
        padding: 1;
    }
    .prompt-title {
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }
    #prompt-hint {
        height: 1;
        color: $text-muted;
        margin-top: 1;
    }
    """

    def __init__(self, title: str, value: str = "", **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.title_text = title
        self.value = value

    def compose(self) -> ComposeResult:
        with Vertical(id="prompt-dialog"):
            yield Label(self.title_text, classes="prompt-title")
            yield Input(value=self.value, id="prompt-input")
            yield Label("Enter to accept, Esc to cancel", id="prompt-hint")

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def key_escape(self) -> None:
        self.dismiss(None)
