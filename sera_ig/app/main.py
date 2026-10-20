"""The root application.

Owns the tabs, the theme, the settings that are shared between panels, and
the command palette. Every panel talks to Instagram through the same client
and the same background-worker helper.
"""

from __future__ import annotations

from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, TabbedContent, TabPane

from ..config import get_config
from .chat import ChatPanel
from .feed import FeedPanel
from .images import resolve_protocol
from .notify import NotifyPanel
from .palette import SeraProvider
from .settings import SettingsPanel
from .stories import StoriesPanel
from .themes import available_themes, resolve_theme, user_themes
from .worker import PanelBase

#: The panels, in tab order.
PANELS = {
    "chats": ("Chats", ChatPanel),
    "feed": ("Feed", FeedPanel),
    "stories": ("Stories", StoriesPanel),
    "notifications": ("Notifications", NotifyPanel),
    "settings": ("Settings", SettingsPanel),
}


class SeraApp(App):
    """The visual interface."""

    TITLE = "seraig"
    SUB_TITLE = "Instagram in your terminal"

    CSS = """
    SeraApp {
        layout: vertical;
    }
    #tabs {
        height: 1fr;
    }
    ContentTab {
        height: 1fr;
    }
    TabPane {
        height: 1fr;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+p", "command_palette", "Commands", show=True),
        Binding("ctrl+t", "cycle_theme", "Theme", show=True),
        Binding("ctrl+r", "refresh", "Refresh", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    COMMANDS = {*App.COMMANDS, SeraProvider}

    def __init__(self, client: Any, initial_screen: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.initial_screen = initial_screen if initial_screen in PANELS else "chats"
        self.config = get_config()
        self._theme_names = available_themes(self.config)
        self._user_themes = user_themes(self.config)
        for theme in self._user_themes.values():
            self.register_theme(theme)

    # ------------------------------------------------------------- options
    @property
    def theme_name(self) -> str:
        """The name of the theme in use."""
        return self.current_theme.name

    @property
    def show_avatars(self) -> bool:
        """Whether the avatars are shown."""
        return bool(self.config.get("ui.show_avatars", True))

    @property
    def show_timestamps(self) -> bool:
        """Whether the timestamps are shown."""
        return bool(self.config.get("ui.show_timestamps", True))

    @property
    def show_previews(self) -> bool:
        """Whether the conversation previews are shown."""
        return bool(self.config.get("ui.show_previews", True))

    @property
    def animations(self) -> bool:
        """Whether the interface animates."""
        return bool(self.config.get("ui.animations", True))

    @property
    def image_protocol_setting(self) -> str:
        """The configured image protocol, before detection."""
        return str(self.config.get("ui.image_protocol", "auto"))

    @property
    def image_protocol(self) -> str:
        """The image protocol actually in use."""
        return resolve_protocol(self.image_protocol_setting)

    # -------------------------------------------------------------- layout
    def compose(self) -> ComposeResult:
        yield Header()
        with TabbedContent(initial=self.initial_screen, id="tabs"):
            for key, (title, panel) in PANELS.items():
                with TabPane(title, id=key):
                    if panel is SettingsPanel:
                        yield panel()
                    else:
                        yield panel(self.client)
        yield Footer()

    def on_mount(self) -> None:
        """Apply the configured theme."""
        wanted = str(self.config.get("ui.theme", "textual-dark"))
        if resolve_theme(wanted, self.config) is not None:
            self.theme = wanted

    # -------------------------------------------------------------- themes
    def set_theme(self, name: str) -> None:
        """Switch to the theme called *name* and remember it."""
        if resolve_theme(name, self.config) is None:
            self.notify(f"No theme called '{name}'", title="Theme", severity="warning")
            return
        self.theme = name
        self.config.set("ui.theme", name)
        self.notify(f"Theme: {name}", title="Theme")

    def cycle_theme(self) -> None:
        """Move to the next theme."""
        names = sorted(set(self._theme_names) | set(self._user_themes))
        if not names:
            return
        try:
            index = names.index(self.theme_name)
        except ValueError:
            index = -1
        self.set_theme(names[(index + 1) % len(names)])

    # ------------------------------------------------------------ settings
    def set_option(self, name: str, value: Any) -> None:
        """Change a setting and remember it."""
        self.config.set(f"ui.{name}", value)
        self.refresh_active()

    def toggle_avatars(self) -> None:
        """Show or hide the avatars."""
        self.set_option("show_avatars", not self.show_avatars)

    def set_image_protocol(self, protocol: str) -> None:
        """Change the image protocol."""
        self.set_option("image_protocol", protocol)

    # ------------------------------------------------------------- actions
    def goto_screen(self, name: str) -> None:
        """Switch to the tab called *name*."""
        if name in PANELS:
            self.query_one("#tabs", TabbedContent).active = name

    def refresh_active(self) -> None:
        """Reload whatever is on screen."""
        panel = self._active_panel()
        if panel is not None and hasattr(panel, "reload"):
            panel.reload()

    def _active_panel(self) -> Any:
        try:
            self.query_one("#tabs", TabbedContent)
        except Exception:  # pragma: no cover - the tabs are not mounted yet
            return None
        for panel in self.query(PanelBase):
            if panel.display and panel.region:
                return panel
        return None

    def report_error(self, exc: BaseException) -> None:
        """Show a failure without taking the application down."""
        from .worker import describe_error

        self.notify(describe_error(exc), title="Error", severity="error", timeout=8)

    def copy_to_clipboard(self, text: str) -> None:
        """Put *text* on the clipboard, if the terminal allows it."""
        try:
            super().copy_to_clipboard(text)
        except Exception:  # pragma: no cover - not every terminal allows it
            self.notify("Could not copy", title="Clipboard", severity="warning")

    def run_cli_command(self, args: list[str]) -> None:
        """Run a one-turn command, handing the terminal over while it runs."""
        from ..cli import run_command_line

        def target() -> None:
            run_command_line(args)

        try:
            with self.suspend():
                target()
        except Exception as exc:  # pragma: no cover - terminal dependent
            self.report_error(exc)

    def action_cycle_theme(self) -> None:
        self.cycle_theme()

    def action_refresh(self) -> None:
        self.refresh_active()

    def action_quit(self) -> None:
        self.exit()
