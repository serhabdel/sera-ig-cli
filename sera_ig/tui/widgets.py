"""Shared curses helpers."""

from __future__ import annotations

import curses
import itertools
from dataclasses import dataclass

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
SPINNER_FRAMES_ASCII = "|/-\\"


def safe_addstr(window: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
    """Write *text* without ever raising at the edges of the window."""
    if not text:
        return
    try:
        height, width = window.getmaxyx()
    except curses.error:  # pragma: no cover - window gone
        return
    if y < 0 or y >= height or x >= width:
        return
    text = text[: max(0, width - x - 1)]
    if not text:
        return
    try:
        window.addstr(y, x, text, attr)
    except curses.error:
        pass


def truncate(text: str, width: int) -> str:
    """Shorten *text* to *width* columns, adding an ellipsis."""
    text = (text or "").replace("\n", " ")
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def spinner_frames() -> tuple[str, ...]:
    """Return the spinner frames the terminal can display."""
    encoding = "utf-8"
    try:
        "⠋".encode(encoding)
    except UnicodeEncodeError:  # pragma: no cover - legacy console
        return tuple(SPINNER_FRAMES_ASCII)
    return tuple(SPINNER_FRAMES)


class Spinner:
    """An animated spinner that advances on every frame."""

    def __init__(self, label: str = "Loading") -> None:
        self.label = label
        self._frames = itertools.cycle(spinner_frames())
        self._frame = next(self._frames)

    def advance(self) -> str:
        """Move to the next frame and return the whole line."""
        self._frame = next(self._frames)
        return f"{self._frame} {self.label}…"

    @property
    def frame(self) -> str:
        """The current frame character."""
        return self._frame


@dataclass
class ScrollState:
    """Tracks the scroll offset of a list of lines."""

    offset: int = 0
    total: int = 0

    def clamp(self, visible: int) -> None:
        """Keep the offset inside the available range."""
        maximum = max(0, self.total - visible)
        self.offset = max(0, min(self.offset, maximum))

    def scroll_up(self, amount: int = 1) -> None:
        self.offset = max(0, self.offset - amount)

    def scroll_down(self, amount: int = 1, visible: int = 1) -> None:
        self.offset = min(max(0, self.total - visible), self.offset + amount)

    def to_bottom(self, visible: int) -> None:
        self.offset = max(0, self.total - visible)


class Pane:
    """A simple bordered pane with a title."""

    def __init__(self, window: curses.window, y: int, x: int, height: int, width: int, title: str = "") -> None:
        self.window = window
        self.y = y
        self.x = x
        self.height = height
        self.width = width
        self.title = title

    def draw_border(self, attr: int = 0) -> None:
        """Draw the box around the pane."""
        if self.height < 2 or self.width < 2:
            return
        for column in range(self.x, self.x + self.width):
            safe_addstr(self.window, self.y, column, "─")
            safe_addstr(self.window, self.y + self.height - 1, column, "─")
        for row in range(self.y, self.y + self.height):
            safe_addstr(self.window, row, self.x, "│")
            safe_addstr(self.window, row, self.x + self.width - 1, "│")
        safe_addstr(self.window, self.y, self.x, "┌")
        safe_addstr(self.window, self.y, self.x + self.width - 1, "┐")
        safe_addstr(self.window, self.y + self.height - 1, self.x, "└")
        safe_addstr(self.window, self.y + self.height - 1, self.x + self.width - 1, "┘")
        if self.title:
            label = f" {self.title} "
            safe_addstr(self.window, self.y, self.x + 2, label, attr)

    @property
    def inner_width(self) -> int:
        return max(0, self.width - 2)

    @property
    def inner_height(self) -> int:
        return max(0, self.height - 2)


def init_colors() -> None:
    """Initialise the colour pairs used by the TUIs."""
    if not curses.has_colors():
        return
    try:
        curses.start_color()
        curses.use_default_colors()
    except curses.error:  # pragma: no cover - limited terminals
        return
    pairs = {
        1: (curses.COLOR_CYAN, -1),  # accents
        2: (curses.COLOR_GREEN, -1),  # success / own messages
        3: (curses.COLOR_YELLOW, -1),  # highlights
        4: (curses.COLOR_MAGENTA, -1),  # titles
        5: (curses.COLOR_RED, -1),  # errors
        6: (curses.COLOR_BLACK, curses.COLOR_WHITE),  # selection
    }
    for index, (foreground, background) in pairs.items():
        try:
            curses.init_pair(index, foreground, background)
        except curses.error:  # pragma: no cover - limited terminals
            pass


def attr(index: int) -> int:
    """Return the attribute for a colour pair."""
    try:
        return curses.color_pair(index)
    except curses.error:  # pragma: no cover - limited terminals
        return 0
