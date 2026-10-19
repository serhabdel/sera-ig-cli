"""TUI logic tests.

The curses layer itself is hard to test, so the pure logic behind it —
message rendering, wrapping, thread selection — is covered here, together
with a regression test for the blank-screen bug.
"""

from __future__ import annotations

import threading
import time

from sera_ig.tui.chat import ChatTUI, _wrap
from sera_ig.tui.feed import FeedTUI
from sera_ig.tui.tasks import Background
from sera_ig.tui.widgets import Spinner

from .fakes import FakeClient


def settle(tui: ChatTUI | FeedTUI, timeout: float = 5.0) -> None:
    """Wait for the background jobs to finish and apply their results."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if isinstance(tui, ChatTUI):
            tui._collect_threads()
            tui._collect_messages()
            busy = tui._busy
        else:
            tui._collect()
            busy = tui._busy
        if not busy:
            return
        time.sleep(0.01)


def settle_background(background: Background, timeout: float = 5.0) -> None:
    """Wait for a bare background job to finish."""
    deadline = time.time() + timeout
    while background.busy and time.time() < deadline:
        time.sleep(0.01)


# ------------------------------------------------------------------- helpers
def test_wrap_breaks_long_lines() -> None:
    lines = _wrap("a" * 50, 20)
    assert all(len(line) <= 20 for line in lines)
    assert "".join(lines) == "a" * 50


def test_wrap_keeps_explicit_newlines() -> None:
    assert _wrap("one\ntwo", 20) == ["one", "two"]


def test_wrap_handles_empty_text() -> None:
    assert _wrap("", 20) == [""]


def test_spinner_advances() -> None:
    spinner = Spinner("Loading")
    first = spinner.advance()
    second = spinner.advance()
    assert first != second
    assert "Loading" in first


# ------------------------------------------------------------------ background
def test_background_runs_a_job() -> None:
    background = Background()
    background.start(lambda: 42)
    settle_background(background)
    result, error = background.take()
    assert result == 42
    assert error is None


def test_background_reports_errors() -> None:
    background = Background()

    def boom() -> None:
        raise ValueError("nope")

    background.start(boom)
    deadline = time.time() + 5
    while background.busy and time.time() < deadline:
        time.sleep(0.01)
    result, error = background.take()
    assert result is None
    assert isinstance(error, ValueError)


def test_background_does_not_block_the_caller() -> None:
    """The call must return immediately, even if the job takes a while."""
    background = Background()
    started = threading.Event()
    release = threading.Event()

    def slow() -> str:
        started.set()
        release.wait(5)
        return "done"

    background.start(slow)
    assert started.wait(2) is True
    assert background.busy is True
    release.set()


# ----------------------------------------------------------------------- chat
def test_chat_tui_lists_threads(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._start_load_threads()
    settle(tui)
    assert len(tui.threads) == 3
    assert tui.threads[0]["title"] in {"noor", "Weekend plans"}


def test_chat_tui_opens_a_thread(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._start_load_threads()
    settle(tui)
    tui.selected = 0
    tui._open_thread(tui.threads[0])
    settle(tui)
    assert tui.current_thread is not None
    assert tui.messages


def test_chat_tui_renders_message_lines(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._start_load_threads()
    settle(tui)
    tui.selected = 0
    tui._open_thread(tui.threads[0])
    settle(tui)
    lines = tui._message_lines()
    assert lines
    joined = " ".join(text for text, _ in lines)
    assert "hey there" in joined


def test_chat_tui_sends_a_message(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._start_load_threads()
    settle(tui)
    tui.selected = 0
    tui._open_thread(tui.threads[0])
    settle(tui)
    tui.focus = "input"
    tui.buffer = "from the tui"
    tui._on_enter()
    assert fake_client.sent[-1]["text"] == "from the tui"
    assert tui.buffer == ""


def test_chat_tui_refuses_to_send_without_a_thread(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui.buffer = "hello"
    tui._on_enter()
    assert fake_client.sent == []
    assert "Pick a conversation" in tui.status


def test_chat_tui_quit_command(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._run_command("q")
    assert tui._running is False


def test_chat_tui_unknown_command(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._run_command("nonsense")
    assert "unknown command" in tui.status


def test_chat_tui_reports_a_failed_load(fake_client: FakeClient) -> None:
    """A failing API call must show an error, not a blank screen."""

    def boom(*args, **kwargs):
        raise RuntimeError("network down")

    tui = ChatTUI(fake_client)
    tui._fetch_threads = boom  # type: ignore[method-assign]
    tui._start_load_threads()
    settle(tui)
    assert "network down" in tui.status


def test_chat_tui_is_busy_while_loading(fake_client: FakeClient) -> None:
    """The interface must report being busy before the network answers."""
    release = threading.Event()

    def slow(*args, **kwargs):
        release.wait(5)
        return []

    tui = ChatTUI(fake_client)
    tui._fetch_threads = slow  # type: ignore[method-assign]
    tui._start_load_threads()
    assert tui._busy is True
    release.set()
    settle(tui)
    assert tui._busy is False


# ----------------------------------------------------------------------- feed
def test_feed_tui_loads_the_timeline(fake_client: FakeClient) -> None:
    tui = FeedTUI(fake_client)
    tui._load()
    settle(tui)
    assert len(tui.items) == 1
    assert tui.items[0]["code"] == "ABC123"
