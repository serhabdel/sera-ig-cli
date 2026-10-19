"""Thread resolution tests."""

from __future__ import annotations

import pytest

from sera_ig.errors import NotFoundError, UsageError
from sera_ig.resolve import looks_like_thread_id, resolve_thread, thread_title

from .fakes import FakeClient, make_thread


def test_thread_id_is_detected() -> None:
    assert looks_like_thread_id("340282366841510300949128268610842297468") is True
    assert looks_like_thread_id("abdel") is False


def test_resolve_by_exact_thread_id(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "340282366841510300949128268610842297468")
    assert thread.id == "340282366841510300949128268610842297468"


def test_resolve_by_username(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "abdel")
    assert "abdel" in [u.username for u in thread.users]


def test_resolve_by_username_with_at_sign(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "@abdel")
    assert thread.id == "340282366841510300949128268610842297468"


def test_resolve_by_title(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "Weekend plans")
    assert thread.thread_title == "Weekend plans"


def test_resolve_is_case_insensitive(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "WEEKEND PLANS")
    assert thread.thread_title == "Weekend plans"


def test_resolve_by_partial_username(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "sara")
    assert "sara" in [u.username for u in thread.users]


def test_resolve_unknown_raises(fake_client: FakeClient) -> None:
    with pytest.raises(NotFoundError):
        resolve_thread(fake_client, "definitely-not-a-user-xyz")


def test_resolve_empty_raises(fake_client: FakeClient) -> None:
    with pytest.raises(UsageError):
        resolve_thread(fake_client, "  ")


def test_resolve_creates_thread_for_new_user(fake_client: FakeClient) -> None:
    thread = resolve_thread(fake_client, "brandnewperson", create=True)
    assert thread.id == "340282366841510300949128268610842297471"


def test_thread_title_falls_back_to_usernames() -> None:
    thread = make_thread(usernames=["ana", "bo"], title="")
    assert thread_title(thread) == "ana, bo"
