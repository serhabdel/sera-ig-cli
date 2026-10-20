"""Tests for how many requests the client makes.

Every call to Instagram is a round trip that costs a second or more, so the
number of requests is part of the user experience. These tests pin it down.
"""

from __future__ import annotations

from typing import Any

from sera_ig import api
from sera_ig.resolve import resolve_thread

from .fakes import FakeClient


class CountingClient(FakeClient):
    """A client that records every call it receives."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def direct_threads(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append("direct_threads")
        return super().direct_threads(*args, **kwargs)

    def direct_threads_chunk(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append("direct_threads_chunk")
        return super().direct_threads_chunk(*args, **kwargs)

    def direct_thread(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append("direct_thread")
        return super().direct_thread(*args, **kwargs)

    def direct_messages(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append("direct_messages")
        return super().direct_messages(*args, **kwargs)

    def direct_send(self, *args: Any, **kwargs: Any) -> Any:
        self.calls.append("direct_send")
        return super().direct_send(*args, **kwargs)


def test_listing_the_inbox_is_one_request() -> None:
    client = CountingClient()
    records = api.list_threads(client, amount=20, message_limit=1)
    assert records
    assert client.calls == ["direct_threads"]


def test_opening_a_conversation_is_one_request() -> None:
    """A thread and its messages come back in the same round trip."""
    client = CountingClient()
    thread, messages = api.open_thread(client, "340282366841510300949128268610842297468")
    assert thread is not None
    assert messages
    assert client.calls == ["direct_thread"]


def test_resolving_a_known_thread_id_is_one_request() -> None:
    """A thread id must not trigger a listing of the whole inbox."""
    client = CountingClient()
    resolve_thread(client, "340282366841510300949128268610842297468")
    assert client.calls == ["direct_thread"]


def test_resolving_a_username_stops_at_the_first_page() -> None:
    client = CountingClient()
    resolve_thread(client, "noor")
    assert client.calls == ["direct_threads_chunk"]


def test_sending_a_message_needs_no_lookup() -> None:
    """The thread is already known, so sending must not resolve it again."""
    client = CountingClient()
    thread = client.direct_thread(340282366841510300949128268610842297468, amount=1)
    client.calls.clear()
    api.send_text(client, thread, "hello")
    assert client.calls == ["direct_send"]


def test_replying_costs_the_reply_lookup_and_the_send() -> None:
    client = CountingClient()
    # The second thread holds the message 9002.
    thread = client.direct_thread(340282366841510300949128268610842297469, amount=1)
    client.calls.clear()
    api.send_text(client, thread, "sure", reply_to={"id": "9002"})
    assert client.calls == ["direct_thread", "direct_send"]
