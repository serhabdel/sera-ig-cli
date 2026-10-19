"""A scrollable feed TUI — ``seraig tui feed``."""

from __future__ import annotations

import curses
import time
from typing import Any

from .. import api
from ..output import format_time
from .tasks import Background
from .widgets import Pane, ScrollState, Spinner, attr, init_colors, safe_addstr, truncate

REFRESH_SECONDS = 30


class FeedTUI:
    """Browse the home timeline from the terminal."""

    def __init__(self, client: Any) -> None:
        self.client = client
        self.items: list[dict[str, Any]] = []
        self.selected = 0
        self.scroll = ScrollState()
        self.status = ""
        self._running = True
        self._screen_size = (24, 80)
        self._last_refresh = 0.0
        self._background = Background()
        self._spinner = Spinner("Loading feed")

    @property
    def _busy(self) -> bool:
        """Whether the feed is still loading."""
        return self._background.busy

    def run(self) -> None:
        """Start the TUI."""
        curses.wrapper(self._main)

    def _main(self, screen: curses.window) -> None:
        init_colors()
        screen.keypad(True)
        try:
            curses.curs_set(0)
        except curses.error:  # pragma: no cover - terminal dependent
            pass
        screen.timeout(250)
        self._last_refresh = time.time()
        self._load()

        while self._running:
            self._draw(screen)
            self._collect()
            try:
                key = screen.getch()
            except KeyboardInterrupt:  # pragma: no cover - defensive
                break
            if key == -1:
                if time.time() - self._last_refresh > REFRESH_SECONDS and not self._busy:
                    self._last_refresh = time.time()
                    self._load()
                continue
            if key in (3, 4):  # ctrl-c / ctrl-d
                break
            if key in (curses.KEY_UP, ord("k")):
                self.selected = max(0, self.selected - 1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self.selected = min(max(0, len(self.items) - 1), self.selected + 1)
            elif key == curses.KEY_PPAGE:
                self.selected = max(0, self.selected - 10)
            elif key == curses.KEY_NPAGE:
                self.selected = min(max(0, len(self.items) - 1), self.selected + 10)
            elif key == ord("r"):
                self._load()
            elif key == ord("q"):
                break
            elif key == curses.KEY_RESIZE:
                continue

    def _load(self) -> None:
        """Fetch the timeline in the background."""
        self._background.start(self._fetch)

    def _fetch(self) -> list[dict[str, Any]]:
        return api.timeline(self.client, amount=40)

    def _collect(self) -> None:
        """Apply whatever the background job produced."""
        finished = self._background.take()
        if finished is None:
            return
        result, error = finished
        if error is not None:
            self.status = str(error)
            return
        self.items = result or []
        if self.selected >= len(self.items):
            self.selected = max(0, len(self.items) - 1)

    def _draw(self, screen: curses.window) -> None:
        self._screen_size = screen.getmaxyx()
        height, width = self._screen_size
        screen.erase()

        list_width = max(30, min(46, width // 2))
        list_pane = Pane(screen, 0, 0, height - 1, list_width, title="Feed")
        detail_pane = Pane(screen, 0, list_width, height - 1, max(10, width - list_width), title="Post")
        list_pane.draw_border(attr(4))
        detail_pane.draw_border(attr(4))

        if self._busy and not self.items:
            safe_addstr(list_pane.window, list_pane.y + 1, list_pane.x + 1, self._spinner.advance(), attr(3))
        else:
            self._draw_list(list_pane)

        self._draw_detail(detail_pane)
        safe_addstr(
            screen,
            height - 1,
            0,
            truncate(self.status or "↑↓ move   r refresh   q quit", width - 1),
            attr(5) if self.status else curses.A_DIM,
        )
        screen.refresh()

    def _draw_list(self, pane: Pane) -> None:
        if not self.items:
            safe_addstr(pane.window, pane.y + 1, pane.x + 1, "Nothing to show.", curses.A_DIM)
            return
        visible = pane.inner_height
        self.scroll.total = len(self.items)
        self.scroll.clamp(visible)
        for row in range(visible):
            index = self.scroll.offset + row
            if index >= len(self.items):
                break
            item = self.items[index]
            user = item.get("user") or {}
            label = truncate(f"@{user.get('username', '')}", pane.inner_width - 2)
            if index == self.selected:
                safe_addstr(pane.window, pane.y + 1 + row, pane.x + 1, label, attr(6))
            else:
                safe_addstr(pane.window, pane.y + 1 + row, pane.x + 1, label)
            caption = truncate(item.get("caption", ""), pane.inner_width - 2)
            if row + 2 < visible:
                safe_addstr(
                    pane.window,
                    pane.y + 2 + row,
                    pane.x + 1,
                    caption,
                    curses.A_DIM,
                )

    def _draw_detail(self, pane: Pane) -> None:
        if not self.items:
            safe_addstr(pane.window, pane.y + 1, pane.x + 1, "Nothing to show.", curses.A_DIM)
            return
        item = self.items[min(self.selected, len(self.items) - 1)]
        user = item.get("user") or {}
        width = pane.inner_width
        y = pane.y + 1
        for line in (
            f"@{user.get('username', '')} ({item.get('kind', 'post')})",
            format_time(item.get("taken_at")),
            "",
            f"♥ {item.get('like_count', 0)}   💬 {item.get('comment_count', 0)}",
            "",
        ):
            safe_addstr(pane.window, y, pane.x + 1, truncate(line, width))
            y += 1
        for line in (item.get("caption") or "").split("\n"):
            for chunk in _wrap(line, width):
                safe_addstr(pane.window, y, pane.x + 1, chunk)
                y += 1
        y += 1
        safe_addstr(pane.window, y, pane.x + 1, truncate(item.get("url", ""), width), attr(1))


def _wrap(text: str, width: int) -> list[str]:
    width = max(10, width)
    out: list[str] = []
    for paragraph in (text or "").split("\n"):
        while len(paragraph) > width:
            cut = paragraph.rfind(" ", 0, width) or width
            out.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()
        out.append(paragraph)
    return out


def run(client: Any) -> None:
    """Entry point used by the CLI."""
    FeedTUI(client).run()


__all__ = ["FeedTUI", "run"]
