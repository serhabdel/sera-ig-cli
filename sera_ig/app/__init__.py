"""The interactive terminal application.

The one-turn commands (``seraig inbox``, ``seraig send …``) are the stable
contract that scripts and agents depend on, and they are unaffected by
anything in here. This package is the graphical surface on top of the same
data layer.
"""

from __future__ import annotations

__all__ = ["run_app", "APP_NAME", "SCREENS"]

APP_NAME = "seraig"

#: The screens the application can show, in tab order.
SCREENS = ("chats", "feed", "stories", "notifications", "settings")


def run_app(client: object, screen: str | None = None) -> None:
    """Launch the application for *client*, optionally focused on *screen*."""
    from .main import SeraApp

    SeraApp(client, initial_screen=screen).run()
