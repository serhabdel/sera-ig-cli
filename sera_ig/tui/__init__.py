"""Terminal user interfaces.

The TUI is built on :mod:`curses`, which ships with Python everywhere except
Windows — there it comes from the ``windows-curses`` package. If neither is
available the interfaces degrade into a clear error instead of an ImportError
traceback, so the one-turn commands keep working everywhere.
"""

from ..errors import SeraError

_MESSAGE = (
    "The interactive interface needs the curses module, which is not available "
    "on this system. On Windows, install it with: pip install windows-curses"
)

try:
    from .chat import ChatTUI
    from .chat import run as run_chat
    from .feed import FeedTUI
    from .feed import run as run_feed

    _IMPORT_ERROR: Exception | None = None
except ImportError as exc:  # pragma: no cover - platform dependent
    _IMPORT_ERROR = exc
    ChatTUI = None  # type: ignore[assignment]
    FeedTUI = None  # type: ignore[assignment]

    def run_chat(*args, **kwargs):  # type: ignore[misc]
        """Raise a friendly error when curses is missing."""
        raise SeraError(_MESSAGE)

    def run_feed(*args, **kwargs):  # type: ignore[misc]
        """Raise a friendly error when curses is missing."""
        raise SeraError(_MESSAGE)


def curses_available() -> bool:
    """Return whether the TUI can run on this system."""
    return _IMPORT_ERROR is None


__all__ = [
    "ChatTUI",
    "FeedTUI",
    "run_chat",
    "run_feed",
    "curses_available",
]
