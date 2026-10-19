"""Data-layer tests: model normalisation and the API helpers."""

from __future__ import annotations

import pytest

from sera_ig import api
from sera_ig.errors import NotFoundError, UsageError
from sera_ig.models import media_to_dict, message_to_dict, thread_to_dict

from .fakes import FakeClient, make_message, make_thread


# ------------------------------------------------------------------- models
def test_message_to_dict_extracts_text() -> None:
    record = message_to_dict(make_message("1", "hello"))
    assert record["text"] == "hello"
    assert record["kind"] == "text"
    assert record["id"] == "1"


def test_message_to_dict_handles_none() -> None:
    assert message_to_dict(None) == {}


def test_thread_to_dict_lists_usernames() -> None:
    record = thread_to_dict(make_thread(usernames=["ana", "bo"], title="Trip"))
    assert record["title"] == "Trip"
    assert record["usernames"] == ["ana", "bo"]
    assert record["is_group"] is True


def test_media_to_dict_contains_code_and_url() -> None:
    from .fakes import make_media

    record = media_to_dict(make_media())
    assert record["code"] == "ABC123"
    assert record["url"] == "https://www.instagram.com/p/ABC123/"
    assert record["kind"] == "post"


# ---------------------------------------------------------------------- api
def test_list_threads_returns_records(fake_client: FakeClient) -> None:
    records = api.list_threads(fake_client, amount=10)
    assert len(records) == 3
    assert {r["title"] for r in records} >= {"abdel", "Weekend plans"}


def test_list_threads_filters_by_search(fake_client: FakeClient) -> None:
    records = api.list_threads(fake_client, amount=10, search="sara")
    assert len(records) == 1
    assert records[0]["usernames"] == ["sara", "omar"]


def test_read_messages_is_oldest_first(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "Weekend plans")
    records = api.read_messages(fake_client, thread, limit=10)
    assert [r["text"] for r in records] == ["saturday?", "works for me"]


def test_send_text_records_the_call(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "abdel")
    record = api.send_text(fake_client, thread, "hi there")
    assert record["text"] == "hi there"
    assert fake_client.sent[-1]["thread_ids"] == [int(thread.id)]


def test_send_text_as_reply(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "Weekend plans")
    api.send_text(fake_client, thread, "sure", reply_to={"id": "9002"})
    assert fake_client.sent[-1]["reply_to"] == "9002"


def test_reply_to_missing_message_raises(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "abdel")
    with pytest.raises(NotFoundError):
        api.send_text(fake_client, thread, "sure", reply_to={"id": "does-not-exist"})


def test_react_and_unsend(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "abdel")
    api.react(fake_client, thread, "9001", "🔥")
    api.unsend(fake_client, thread, "9001")
    assert fake_client.reactions[-1]["emoji"] == "🔥"
    assert fake_client.unsent[-1]["message_id"] == 9001


def test_mark_seen(fake_client: FakeClient) -> None:
    thread = api.get_thread(fake_client, "abdel")
    api.mark_seen(fake_client, thread)
    assert fake_client.seen_threads == [int(thread.id)]


def test_search_users(fake_client: FakeClient) -> None:
    records = api.search_users(fake_client, "abdel")
    assert [r["username"] for r in records] == ["abdel", "abdelhamid"]


def test_timeline(fake_client: FakeClient) -> None:
    records = api.timeline(fake_client, amount=5)
    assert len(records) == 1
    assert records[0]["code"] == "ABC123"


def test_reels(fake_client: FakeClient) -> None:
    records = api.reels(fake_client, amount=5)
    assert records[0]["kind"] == "reel"


def test_stories_tray(fake_client: FakeClient) -> None:
    tray = api.stories_tray(fake_client)
    assert len(tray) == 1
    assert tray[0]["user"]["username"] == "abdel"
    assert tray[0]["story_count"] == 1


def test_user_stories(fake_client: FakeClient) -> None:
    stories = api.user_stories(fake_client, "abdel")
    assert len(stories) == 1
    assert stories[0]["kind"] == "photo"


def test_notifications(fake_client: FakeClient) -> None:
    records = api.notifications(fake_client)
    assert records[0]["type"] == "like"
    assert records[0]["user"]["username"] == "sara"


def test_user_profile(fake_client: FakeClient) -> None:
    record = api.user_profile(fake_client, "abdel")
    assert record["username"] == "abdel"
    assert record["followers"] == 345
    assert record["url"] == "https://www.instagram.com/abdel/"


def test_user_posts(fake_client: FakeClient) -> None:
    records = api.user_posts(fake_client, "abdel", amount=3)
    assert len(records) == 1


def test_media_info_accepts_code(fake_client: FakeClient) -> None:
    record = api.media_info(fake_client, "ABC123")
    assert record["code"] == "ABC123"


def test_media_info_accepts_url(fake_client: FakeClient) -> None:
    record = api.media_info(fake_client, "https://www.instagram.com/p/ABC123/")
    assert record["code"] == "ABC123"


def test_media_info_rejects_garbage(fake_client: FakeClient) -> None:
    with pytest.raises(NotFoundError):
        api.media_info(fake_client, "not-a-media")


def test_resolve_media_pk_requires_a_reference(fake_client: FakeClient) -> None:
    with pytest.raises(UsageError):
        api.resolve_media_pk(fake_client, "")


def test_comment_media(fake_client: FakeClient) -> None:
    record = api.comment_media(fake_client, "ABC123", "nice")
    assert record["text"] == "nice"


def test_download_media(fake_client: FakeClient, tmp_path) -> None:
    path = api.download_media(fake_client, "ABC123", tmp_path)
    assert path.exists()
    assert path.read_bytes() == b"jpeg"
