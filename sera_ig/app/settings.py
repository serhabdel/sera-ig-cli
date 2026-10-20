"""The Settings panel — theme, images, density and the key map."""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Label, Select, Static, Switch

from .images import PROTOCOLS
from .themes import available_themes

#: Every key the application answers to, with a short description.
KEYMAP: tuple[tuple[str, str], ...] = (
    ("ctrl+p", "Open the command palette"),
    ("ctrl+t", "Cycle to the next theme"),
    ("ctrl+r", "Reload what is on screen"),
    ("ctrl+f", "Focus the conversation filter"),
    ("ctrl+enter", "Send the message being written"),
    ("ctrl+q", "Quit"),
    ("tab", "Move between panes"),
    ("↑ ↓ / j k", "Move through a list"),
    ("enter", "Open, or send"),
    ("escape", "Close the overlay, or drop the selection"),
    ("click", "Open a conversation, or select a message"),
    ("double click", "Copy a message"),
    ("scroll", "Scroll the list or the conversation"),
)


class SettingsPanel(Static):
    """The settings screen."""

    DEFAULT_CSS = """
    SettingsPanel {
        layout: vertical;
    }
    #settings-body {
        height: 1fr;
        padding: 1 2;
    }
    .settings-heading {
        text-style: bold;
        color: $accent;
        margin: 1 0 0 0;
    }
    .settings-row {
        height: auto;
        margin: 0 0 1 0;
    }
    .settings-label {
        width: 22;
        content-align: left middle;
    }
    .settings-control {
        width: 1fr;
    }
    .keymap-entry {
        color: $text-muted;
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:
        themes = available_themes()
        current = self.app.theme_name
        with VerticalScroll(id="settings-body"):
            yield Label("Appearance", classes="settings-heading")
            with Horizontal(classes="settings-row"):
                yield Label("Theme", classes="settings-label")
                yield Select(
                    [(name, name) for name in themes],
                    value=current if current in themes else Select.BLANK,
                    allow_blank=False,
                    id="theme-select",
                    classes="settings-control",
                )
            with Horizontal(classes="settings-row"):
                yield Label("Image protocol", classes="settings-label")
                yield Select(
                    [(name, name) for name in PROTOCOLS],
                    value=self.app.image_protocol_setting,
                    allow_blank=False,
                    id="protocol-select",
                    classes="settings-control",
                )
            with Horizontal(classes="settings-row"):
                yield Label("Show avatars", classes="settings-label")
                yield Switch(value=self.app.show_avatars, id="avatar-switch")
            with Horizontal(classes="settings-row"):
                yield Label("Show timestamps", classes="settings-label")
                yield Switch(value=self.app.show_timestamps, id="timestamp-switch")
            with Horizontal(classes="settings-row"):
                yield Label("Show previews", classes="settings-label")
                yield Switch(value=self.app.show_previews, id="preview-switch")
            with Horizontal(classes="settings-row"):
                yield Label("Animations", classes="settings-label")
                yield Switch(value=self.app.animations, id="animation-switch")

            yield Label("Key map", classes="settings-heading")
            for key, description in KEYMAP:
                yield Label(
                    Text.assemble((f"{key:<16}", "bold cyan"), (description, "dim")),
                    classes="keymap-entry",
                )

    def on_select_changed(self, event: Select.Changed) -> None:
        """Apply a change as soon as it is made."""
        if event.select.id == "theme-select" and event.value is not Select.BLANK:
            self.app.set_theme(str(event.value))
        elif event.select.id == "protocol-select" and event.value is not Select.BLANK:
            self.app.set_image_protocol(str(event.value))

    def on_switch_changed(self, event: Switch.Changed) -> None:
        """Apply a toggle as soon as it is flipped."""
        mapping = {
            "avatar-switch": ("show_avatars",),
            "timestamp-switch": ("show_timestamps",),
            "preview-switch": ("show_previews",),
            "animation-switch": ("animations",),
        }
        names = mapping.get(event.switch.id or "")
        if names:
            self.app.set_option(names[0], event.value)
