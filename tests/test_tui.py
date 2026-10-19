"""TUI logic tests.

The curses layer itself is hard to test, so the pure logic behind it —
message rendering, wrapping, thread selection — is covered here.
"""

from __future__ import annotations

from sera_ig.tui.chat import ChatTUI, _wrap
from sera_ig.tui.feed import FeedTUI

from .fakes import FakeClient


def test_wrap_breaks_long_lines() -> None:
    lines = _wrap("a" * 50, 20)
    assert all(len(line) <= 20 for line in lines)
    assert "".join(lines) == "a" * 50


def test_wrap_keeps_explicit_newlines() -> None:
    assert _wrap("one\ntwo", 20) == ["one", "two"]


def test_wrap_handles_empty_text() -> None:
    assert _wrap("", 20) == [""]


def test_chat_tui_lists_threads(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._load_threads()
    assert len(tui.threads) == 3
    assert tui.threads[0]["title"] in {"abdel", "Weekend plans"}


def test_chat_tui_opens_a_thread(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._load_threads()
    tui.selected = 0
    tui._open_selected()
    assert tui.current_thread is not None
    assert tui.messages


def test_chat_tui_renders_message_lines(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._load_threads()
    tui.selected = 0
    tui._open_selected()
    lines = tui._message_lines()
    assert lines
    joined = " ".join(text for text, _ in lines)
    assert "hey there" in joined


def test_chat_tui_sends_a_message(fake_client: FakeClient) -> None:
    tui = ChatTUI(fake_client)
    tui._load_threads()
    tui.selected = 0
    tui._open_selected()
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


def test_feed_tui_loads_the_timeline(fake_client: FakeClient) -> None:
    tui = FeedTUI(fake_client)
    tui._load()
    assert len(tui.items) == 1
    assert tui.items[0]["code"] == "ABC123"
