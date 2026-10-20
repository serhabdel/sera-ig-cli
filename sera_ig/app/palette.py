"""The command palette.

Ctrl+P opens Textual's palette. This provider adds two kinds of entry:

* **app actions** — switch screen, change theme, refresh, toggle avatars;
* **CLI commands** — every one-turn command, so the palette can drive the
  exact same surface the shell and the terminal use.
"""

from __future__ import annotations

from typing import Any

from textual.command import DiscoveryHit, Hit, Hits, Provider

#: The one-turn commands offered in the palette, with their help text.
CLI_COMMANDS: dict[str, str] = {
    "inbox": "List your direct-message conversations",
    "read": "Read the messages of a conversation",
    "send": "Send a message to a conversation",
    "reply": "Reply to a specific message",
    "react": "React to a message with an emoji",
    "unsend": "Unsend a message you sent",
    "seen": "Mark a conversation as read",
    "search": "Search Instagram for people",
    "feed": "Show posts from the people you follow",
    "reels": "Show reels",
    "stories": "Show stories",
    "notify": "Show recent activity",
    "user": "Show a profile summary",
    "posts": "Show the latest posts of an account",
    "post": "Show the details of a post",
    "like": "Like a post",
    "comment": "Comment on a post",
    "comments": "List the comments of a post",
    "download": "Download a photo or video",
    "theme": "List, set and inspect themes",
    "config": "Read and write the configuration",
    "doctor": "Check the installation and the stored sessions",
}


class SeraProvider(Provider):
    """Offers app actions and the one-turn CLI commands."""

    async def discover(self) -> Hits:
        """Show the app actions when the palette is opened empty."""
        for name, help_text, callback in self._app_actions():
            yield DiscoveryHit(name, callback, help=help_text)

    async def search(self, query: str) -> Hits:
        """Show everything that matches *query*."""
        if not query.strip():
            # The fuzzy matcher cannot score an empty query.
            for name, help_text, callback in self._app_actions():
                yield DiscoveryHit(name, callback, help=help_text)
            return

        matcher = self.matcher(query)

        for name, help_text, callback in self._app_actions():
            if (match := matcher.match(name)) > 0:
                yield Hit(match, matcher.highlight(name), callback, help=help_text)

        for name, help_text in CLI_COMMANDS.items():
            label = f"seraig {name}"
            if (match := matcher.match(label)) > 0:
                yield Hit(
                    match,
                    matcher.highlight(label),
                    self._cli_callback(name),
                    help=help_text,
                )

    # ------------------------------------------------------------- actions
    def _app_actions(self) -> list[tuple[str, str, Any]]:
        return [
            ("Chats", "Open the conversations", self._goto("chats")),
            ("Feed", "Open the home timeline", self._goto("feed")),
            ("Stories", "Open the stories", self._goto("stories")),
            ("Notifications", "Open the activity feed", self._goto("notifications")),
            ("Settings", "Open the settings", self._goto("settings")),
            (
                "Search messages",
                "Search every message you have received",
                self.app.search_messages,
            ),
            ("Change theme", "Switch to the next theme", self._cycle_theme),
            ("Toggle avatars", "Show or hide the avatars", self._toggle_avatars),
            ("Refresh", "Reload what is on screen", self._refresh),
            ("Quit", "Leave the application", self._quit),
        ]

    def _goto(self, screen: str) -> Any:
        def callback() -> None:
            self.app.goto_screen(screen)

        return callback

    def _cycle_theme(self) -> None:
        self.app.cycle_theme()

    def _toggle_avatars(self) -> None:
        self.app.toggle_avatars()

    def _refresh(self) -> None:
        self.app.refresh_active()

    def _quit(self) -> None:
        self.app.exit()

    def _cli_callback(self, name: str) -> Any:
        def callback() -> None:
            self.app.run_cli_command([name])

        return callback
