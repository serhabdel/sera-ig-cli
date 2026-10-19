"""The interactive chat TUI.

Two panes: the conversation list on the left, the active conversation on the
right, and an input line at the bottom. Everything is keyboard driven.

    seraig tui chat                 open the TUI
    seraig tui chat abdel          open straight into a conversation

Every call to Instagram happens on a worker thread, so the interface is
drawn immediately and keeps animating while the network answers.
"""

from __future__ import annotations

import curses
import time
from typing import Any

from .. import api
from ..errors import SeraError
from ..output import format_time, relative_time
from ..resolve import thread_title
from .tasks import Background
from .widgets import Pane, ScrollState, Spinner, attr, init_colors, safe_addstr, truncate

REFRESH_SECONDS = 15
MESSAGE_PAGE = 50


class ChatTUI:
    """A keyboard-only Instagram Direct client."""

    def __init__(self, client: Any, initial: str | None = None) -> None:
        self.client = client
        self.initial = initial
        self.threads: list[dict[str, Any]] = []
        self.selected = 0
        self.messages: list[dict[str, Any]] = []
        self.current_thread: Any = None
        self.buffer = ""
        self.focus = "input"
        self.thread_scroll = ScrollState()
        self.message_scroll = ScrollState()
        self.status = ""
        self.search = ""
        self.searching = False
        self._running = True
        self._screen_size = (24, 80)
        self._last_refresh = 0.0
        self._threads_bg = Background()
        self._messages_bg = Background()
        self._spinner = Spinner("Loading conversations")
        self._spinner_line = self._spinner.advance()
        self._loading_label = "Loading conversations"
        self._keep_scroll = False

    @property
    def _busy(self) -> bool:
        """Whether any network call is in flight."""
        return self._threads_bg.busy or self._messages_bg.busy

    # ------------------------------------------------------------- lifecycle
    def run(self) -> None:
        """Start the TUI."""
        curses.wrapper(self._main)

    def _main(self, screen: curses.window) -> None:
        init_colors()
        screen.keypad(True)
        try:
            curses.curs_set(1)
        except curses.error:  # pragma: no cover - terminal dependent
            pass
        screen.timeout(250)
        self._last_refresh = time.time()

        if self.initial:
            self._open_initial()
        else:
            self._start_load_threads()

        while self._running:
            self._draw(screen)
            self._collect_threads()
            self._collect_messages()
            try:
                key = screen.getch()
            except KeyboardInterrupt:  # pragma: no cover - defensive
                break
            if key == -1:
                if time.time() - self._last_refresh > REFRESH_SECONDS and not self._busy:
                    self._last_refresh = time.time()
                    self._start_load_threads()
                continue
            self._handle_key(screen, key)

    # ----------------------------------------------------------------- data
    def _start_load_threads(self) -> None:
        """Fetch the conversation list in the background."""
        self._loading_label = "Loading conversations"
        self._spinner.label = self._loading_label
        self._threads_bg.start(self._fetch_threads)

    def _fetch_threads(self) -> list[dict[str, Any]]:
        return api.list_threads(self.client, amount=50, search=self.search or None)

    def _collect_threads(self) -> None:
        """Apply whatever the conversation-list job produced."""
        finished = self._threads_bg.take()
        if finished is None:
            return
        result, error = finished
        if error is not None:
            self.status = _describe(error)
            return
        self.threads = result or []
        if self.selected >= len(self.threads):
            self.selected = max(0, len(self.threads) - 1)
        if self.current_thread is None and self.threads:
            self._open_thread(self.threads[self.selected])

    def _load_messages(self, keep_scroll: bool = False) -> None:
        """Fetch the messages of the open thread in the background."""
        if self.current_thread is None:
            self.messages = []
            return
        self._loading_label = "Loading messages"
        self._spinner.label = self._loading_label
        self._keep_scroll = keep_scroll
        self._messages_bg.start(self._fetch_messages)

    def _fetch_messages(self) -> list[dict[str, Any]]:
        return api.read_messages(self.client, self.current_thread, limit=MESSAGE_PAGE)

    def _collect_messages(self) -> None:
        """Apply whatever the message job produced."""
        finished = self._messages_bg.take()
        if finished is None:
            return
        result, error = finished
        if error is not None:
            self.status = _describe(error)
            return
        if isinstance(result, tuple):
            thread, messages = result
            self.current_thread = thread
            self.messages = messages or []
        else:
            self.messages = result or []
        if not self._keep_scroll:
            self.message_scroll.to_bottom(self._message_pane_height())
        else:
            self.message_scroll.clamp(self._message_pane_height())
        self._keep_scroll = False

    def _open_initial(self) -> None:
        """Open a conversation given on the command line."""
        self._loading_label = "Opening conversation"
        self._spinner.label = self._loading_label
        self._messages_bg.start(self._fetch_initial)

    def _fetch_initial(self) -> tuple[Any, list[dict[str, Any]]]:
        thread = api.get_thread(self.client, self.initial)
        return thread, api.read_messages(self.client, thread, limit=MESSAGE_PAGE)

    def _open_thread(self, record: dict[str, Any]) -> None:
        """Open a conversation from the list."""
        self._loading_label = "Opening conversation"
        self._spinner.label = self._loading_label
        self._messages_bg.start(self._fetch_thread, record["id"])

    def _fetch_thread(self, thread_id: str) -> tuple[Any, list[dict[str, Any]]]:
        thread = api.get_thread(self.client, thread_id)
        return thread, api.read_messages(self.client, thread, limit=MESSAGE_PAGE)

    # --------------------------------------------------------------- layout
    def _layout(self) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int], int]:
        """Return the geometry of the list pane, the message pane and the input row."""
        height, width = self._screen_size
        list_width = max(24, min(38, width // 3))
        input_height = 3
        body_height = max(5, height - input_height - 1)
        list_geo = (1, 0, body_height, list_width)
        message_geo = (1, list_width, body_height, max(10, width - list_width))
        return list_geo, message_geo, input_height

    def _message_pane_height(self) -> int:
        _, message_geo, _ = self._layout()
        return max(1, message_geo[2] - 2)

    # ---------------------------------------------------------------- draw
    def _draw(self, screen: curses.window) -> None:
        self._screen_size = screen.getmaxyx()
        height, width = self._screen_size
        screen.erase()

        # One spinner frame per draw, shared by every pane.
        self._spinner_line = self._spinner.advance()

        list_geo, message_geo, input_height = self._layout()

        list_pane = Pane(screen, *list_geo, title="Conversations")
        message_pane = Pane(screen, *message_geo, title=self._message_title())
        list_pane.draw_border(attr(4))
        message_pane.draw_border(attr(4))

        self._draw_thread_list(list_pane)
        self._draw_messages(message_pane)
        self._draw_input(screen, width, height, input_height)
        self._draw_status(screen, width, height)

        screen.refresh()

    def _message_title(self) -> str:
        if self.current_thread is None:
            return "Conversation"
        return truncate(thread_title(self.current_thread), max(10, self._screen_size[1] // 2))

    def _draw_thread_list(self, pane: Pane) -> None:
        # Each conversation takes two rows: the title and a preview line.
        visible = max(1, pane.inner_height // 2)
        self.thread_scroll.total = len(self.threads)
        if self.selected < self.thread_scroll.offset:
            self.thread_scroll.offset = self.selected
        elif self.selected >= self.thread_scroll.offset + visible:
            self.thread_scroll.offset = self.selected - visible + 1
        self.thread_scroll.clamp(visible)

        if not self.threads:
            # The spinner stays in the wide status bar: a braille glyph is
            # double width and would wrap the narrow pane.
            label = "Loading…" if self._busy else "No conversations"
            safe_addstr(pane.window, pane.y + 1, pane.x + 1, label, attr(3) if self._busy else curses.A_DIM)
            return

        for row in range(visible):
            index = self.thread_scroll.offset + row
            if index >= len(self.threads):
                break
            record = self.threads[index]
            last = record.get("last_message") or {}
            preview = truncate(
                last.get("text") or f"[{last.get('kind', 'message')}]",
                pane.inner_width - 2,
            )
            age = relative_time(record.get("last_activity_at"))
            title = truncate(record["title"], max(4, pane.inner_width - len(age) - 3))
            label = f"{title} ({age})" if age else title
            y = pane.y + 1 + row * 2
            x = pane.x + 1
            if index == self.selected:
                safe_addstr(pane.window, y, x, " " * pane.inner_width, attr(6))
                safe_addstr(pane.window, y, x, label, attr(6) | curses.A_BOLD)
                safe_addstr(pane.window, y + 1, x, preview, attr(6))
            else:
                safe_addstr(pane.window, y, x, label)
                safe_addstr(pane.window, y + 1, x, preview, curses.A_DIM)

    def _draw_messages(self, pane: Pane) -> None:
        if self._busy and not self.messages:
            safe_addstr(pane.window, pane.y + 1, pane.x + 1, self._spinner_line, attr(3))
            return

        lines = self._message_lines()
        visible = pane.inner_height
        self.message_scroll.total = len(lines)
        self.message_scroll.clamp(visible)

        for row in range(visible):
            index = self.message_scroll.offset + row
            if index >= len(lines):
                break
            text, style = lines[index]
            safe_addstr(pane.window, pane.y + 1 + row, pane.x + 1, text, style)

    def _message_lines(self) -> list[tuple[str, int]]:
        """Render the message list into (text, attribute) pairs."""
        if not self.messages:
            return [("No messages yet.", curses.A_DIM)]
        lines: list[tuple[str, int]] = []
        width = max(10, self._screen_size[1] - self._layout()[1][3] - 3)
        for record in self.messages:
            stamp = format_time(record.get("timestamp"))
            mine = bool(record.get("is_sent_by_viewer"))
            body = record.get("text") or ""
            media = record.get("media")
            if media:
                if media.get("url"):
                    body = f"{body}\n{media['url']}".strip()
                elif media.get("pk"):
                    body = f"{body}\npost {media['pk']}".strip()
                else:
                    body = f"{body}\n[media]".strip()
            if record.get("reactions"):
                body = f"{body} {''.join(r['emoji'] for r in record['reactions'])}".strip()

            marker = "▸ " if mine else "▏ "
            prefix = f"{marker}{stamp}  " if stamp else marker
            style = attr(2) if mine else 0
            wrapped = _wrap(body, width - len(prefix) - 1)
            for index, chunk in enumerate(wrapped):
                if index == 0:
                    lines.append((f"{prefix}{chunk}", style))
                else:
                    lines.append((f"{' ' * len(prefix)}{chunk}", style))
            lines.append(("", 0))
        return lines

    def _draw_input(self, screen: curses.window, width: int, height: int, input_height: int) -> None:
        y = height - input_height
        for column in range(width):
            safe_addstr(screen, y, column, "─")
        prompt = "❯ " if self.focus == "input" else "> "
        if self.searching:
            safe_addstr(screen, y + 1, 0, f"search: {self.search}", attr(3))
        else:
            safe_addstr(screen, y + 1, 0, prompt, attr(2))
            safe_addstr(screen, y + 1, len(prompt), truncate(self.buffer, width - len(prompt) - 1))
        if self.focus == "input":
            try:
                curses.setsyx(y + 1, len(prompt) + len(self.buffer))
            except curses.error:  # pragma: no cover - tiny terminals
                pass

    def _draw_status(self, screen: curses.window, width: int, height: int) -> None:
        if self._busy:
            text = self._spinner_line + " — Ctrl-C to cancel"
            safe_addstr(screen, height - 1, 0, truncate(text, width - 1), attr(3))
            return
        hints = "Tab pane  ↑↓ move  Enter open  / search  :q quit"
        if self.status:
            safe_addstr(screen, height - 1, 0, truncate(self.status, width - 1), attr(5))
        else:
            safe_addstr(screen, height - 1, 0, truncate(hints, width - 1), curses.A_DIM)

    # ---------------------------------------------------------------- input
    def _handle_key(self, screen: curses.window, key: int) -> None:
        self.status = ""
        if self.searching:
            self._handle_search_key(key)
            return

        if key == 27:  # escape
            self.buffer = ""
            return
        if key == curses.KEY_RESIZE:
            return
        if key == curses.KEY_BACKSPACE or key in (127, 8):
            self.buffer = self.buffer[:-1]
            return
        if key == curses.KEY_ENTER or key in (10, 13):
            self._on_enter()
            return
        if key == 9:  # tab
            self.focus = "threads" if self.focus == "input" else "input"
            try:
                curses.curs_set(1 if self.focus == "input" else 0)
            except curses.error:  # pragma: no cover
                pass
            return
        if key == curses.KEY_UP:
            self._move(-1)
            return
        if key == curses.KEY_DOWN:
            self._move(1)
            return
        if key == curses.KEY_PPAGE:
            self._scroll_messages(-10)
            return
        if key == curses.KEY_NPAGE:
            self._scroll_messages(10)
            return
        if key == 3:  # ctrl-c
            self._running = False
            return
        if key == 4:  # ctrl-d
            self._running = False
            return
        if key == ord("/"):
            self.searching = True
            self.search = ""
            return
        if key == ord("k") and self.focus == "threads":
            self._move(-1)
            return
        if key == ord("j") and self.focus == "threads":
            self._move(1)
            return
        if 32 <= key <= 126:
            self.buffer += chr(key)

    def _handle_search_key(self, key: int) -> None:
        if key == 27:
            self.searching = False
            self.search = ""
            self._start_load_threads()
            return
        if key in (curses.KEY_ENTER, 10, 13):
            self.searching = False
            self._start_load_threads()
            return
        if key in (curses.KEY_BACKSPACE, 127, 8):
            self.search = self.search[:-1]
            self._start_load_threads()
            return
        if 32 <= key <= 126:
            self.search += chr(key)
            self._start_load_threads()

    def _move(self, delta: int) -> None:
        if not self.threads:
            return
        if self.focus == "threads":
            self.selected = max(0, min(len(self.threads) - 1, self.selected + delta))
            return
        self._scroll_messages(delta)

    def _scroll_messages(self, delta: int) -> None:
        visible = self._message_pane_height()
        if delta < 0:
            self.message_scroll.scroll_up(-delta)
        else:
            self.message_scroll.scroll_down(delta, visible)

    def _on_enter(self) -> None:
        if self.focus == "threads":
            if self.threads:
                self._open_thread(self.threads[self.selected])
            self.focus = "input"
            try:
                curses.curs_set(1)
            except curses.error:  # pragma: no cover
                pass
            return

        text = self.buffer.strip()
        if not text:
            return
        if text.startswith(":"):
            self._run_command(text[1:])
            return
        if self.current_thread is None:
            self.status = "Pick a conversation first."
            return
        try:
            api.send_text(self.client, self.current_thread, text)
            self.buffer = ""
            self._load_messages()
        except SeraError as exc:
            self.status = f"could not send: {exc}"

    def _run_command(self, command: str) -> None:
        """Handle the ``:`` commands."""
        name, _, argument = command.strip().partition(" ")
        name = name.lower()
        if name in {"q", "quit", "exit"}:
            self._running = False
            return
        if name in {"r", "refresh"}:
            self._start_load_threads()
            self.buffer = ""
            return
        self.status = f"unknown command: {name}"
        self.buffer = ""


def _describe(error: BaseException) -> str:
    """Turn an exception into a short line for the status bar."""
    if isinstance(error, SeraError):
        return str(error)
    return f"{type(error).__name__}: {error}"


def _wrap(text: str, width: int) -> list[str]:
    """Wrap *text* to *width* columns, keeping explicit newlines."""
    width = max(10, width)
    out: list[str] = []
    for paragraph in (text or "").split("\n"):
        if not paragraph:
            out.append("")
            continue
        while len(paragraph) > width:
            cut = paragraph.rfind(" ", 0, width)
            if cut <= 0:
                cut = width
            out.append(paragraph[:cut])
            paragraph = paragraph[cut:].lstrip()
        out.append(paragraph)
    return out or [""]


def run(client: Any, initial: str | None = None) -> None:
    """Entry point used by the CLI."""
    ChatTUI(client, initial).run()


__all__ = ["ChatTUI", "run"]
