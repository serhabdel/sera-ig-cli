"""Tests for the new interface features.

Message grouping, the search overlay, the action menu and the read receipts.
"""

from __future__ import annotations

from sera_ig.app.chat import MessageBubble, group_flags
from sera_ig.app.menu import ActionMenu
from sera_ig.app.search import SearchScreen


def message(
    message_id: str,
    *,
    mine: bool = False,
    user: str = "u1",
    timestamp: str = "2026-05-01T11:00:00+00:00",
) -> dict:
    return {
        "id": message_id,
        "text": f"message {message_id}",
        "is_sent_by_viewer": mine,
        "user_id": user,
        "timestamp": timestamp,
        "media": None,
        "reactions": [],
    }


# ------------------------------------------------------------------ grouping
def test_consecutive_messages_from_the_same_person_are_grouped() -> None:
    flags = group_flags(
        [
            message("1", timestamp="2026-05-01T11:00:00+00:00"),
            message("2", timestamp="2026-05-01T11:01:00+00:00"),
        ]
    )
    assert flags == [True, False]


def test_a_different_person_starts_a_new_group() -> None:
    flags = group_flags(
        [
            message("1", user="u1", timestamp="2026-05-01T11:00:00+00:00"),
            message("2", user="u2", timestamp="2026-05-01T11:01:00+00:00"),
        ]
    )
    assert flags == [True, True]


def test_a_long_gap_starts_a_new_group() -> None:
    flags = group_flags(
        [
            message("1", timestamp="2026-05-01T11:00:00+00:00"),
            message("2", timestamp="2026-05-01T12:00:00+00:00"),
        ]
    )
    assert flags == [True, True]


def test_switching_speaker_starts_a_new_group() -> None:
    flags = group_flags(
        [
            message("1", mine=False, timestamp="2026-05-01T11:00:00+00:00"),
            message("2", mine=True, timestamp="2026-05-01T11:00:30+00:00"),
        ]
    )
    assert flags == [True, True]


def test_an_empty_list_has_no_groups() -> None:
    assert group_flags([]) == []


# -------------------------------------------------------------------- bubbles
def test_own_messages_are_marked_as_own() -> None:
    bubble = MessageBubble(message("1", mine=True))
    assert "own" in bubble.classes
    assert "message-bubble" in bubble.classes


def test_other_messages_are_not_marked_as_own() -> None:
    bubble = MessageBubble(message("1"))
    assert "own" not in bubble.classes
    assert "theirs" in bubble.classes


def test_a_grouped_message_is_marked() -> None:
    bubble = MessageBubble(message("1"), grouped=False)
    assert "grouped" in bubble.classes


# ------------------------------------------------------------------- overlays
async def test_the_search_overlay_opens(app) -> None:
    async with app.run_test() as pilot:
        app.search_messages()
        await pilot.pause()
        assert isinstance(app.screen, SearchScreen)
        await pilot.press("escape")
        await pilot.pause()


async def test_the_action_menu_opens(app) -> None:
    async with app.run_test() as pilot:
        app.push_screen(ActionMenu("Message", [("copy", "Copy", "Copy the text")]))
        await pilot.pause()
        assert isinstance(app.screen, ActionMenu)
        await pilot.press("escape")
        await pilot.pause()


async def test_the_search_overlay_shows_results(app, monkeypatch) -> None:
    from sera_ig import api

    monkeypatch.setattr(
        api,
        "search_messages",
        lambda client, query: [
            {
                "id": "1",
                "text": "the answer is 42",
                "timestamp": "2026-05-01T11:00:00+00:00",
                "conversation": {"id": "99", "title": "Maroua"},
            }
        ],
    )

    async with app.run_test() as pilot:
        app.search_messages()
        await pilot.pause()
        from textual.widgets import Input, OptionList

        app.screen.query_one("#search-input", Input).value = "42"
        await pilot.pause(0.4)
        await pilot.pause(0.4)
        listing = app.screen.query_one("#search-results", OptionList)
        assert listing.option_count == 1
        await pilot.press("escape")
        await pilot.pause()


# ------------------------------------------------------------------- stories
def test_the_stories_tray_falls_back_to_asking_the_people_directly() -> None:
    """When the tray endpoint is empty, the people are asked one by one."""
    from sera_ig import api

    class Client:
        def get_reels_tray_feed(self, reason="cold_start"):
            return {"tray": [], "status": "ok"}

        def users_stories_gql(self, user_ids):
            from datetime import datetime, timezone

            from instagrapi.types import Story, UserShort

            user = UserShort(pk="1", username="noor", full_name="Noor")
            user.stories = [
                Story(
                    pk="9",
                    id="9_1",
                    code="S1",
                    taken_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    media_type=1,
                    user=UserShort(pk="1", username="noor", full_name="Noor"),
                    sponsor_tags=[],
                    mentions=[],
                    links=[],
                    hashtags=[],
                    locations=[],
                    stickers=[],
                )
            ]
            return [user]

    records = api.stories_tray(Client(), ["1"])
    assert len(records) == 1
    assert records[0]["user"]["username"] == "noor"


def test_the_stories_tray_reports_the_response_keys() -> None:
    from sera_ig import api

    class Client:
        def get_reels_tray_feed(self, reason="cold_start"):
            return {"tray": [], "reels_tray": {}, "status": "ok"}

    keys = api.stories_raw_keys(Client())
    assert "tray" in keys
    assert "status" in keys


# ------------------------------------------------------------------ sorting
def test_records_are_sorted_by_recency() -> None:
    from sera_ig.models import sort_by_recency

    records = [
        {"name": "old", "last_activity_at": "2026-05-01T10:00:00+00:00"},
        {"name": "new", "last_activity_at": "2026-05-03T10:00:00+00:00"},
        {"name": "middle", "last_activity_at": "2026-05-02T10:00:00+00:00"},
    ]
    assert [r["name"] for r in sort_by_recency(records)] == ["new", "middle", "old"]


def test_timezone_offsets_do_not_break_the_order() -> None:
    """A string comparison gets this wrong; comparing instants does not."""
    from sera_ig.models import sort_by_recency

    records = [
        {"name": "later", "last_activity_at": "2026-05-01T12:30:00+02:00"},
        {"name": "earlier", "last_activity_at": "2026-05-01T10:00:00+00:00"},
    ]
    # 12:30+02:00 is 10:30 UTC, which is after 10:00 UTC.
    assert [r["name"] for r in sort_by_recency(records)] == ["later", "earlier"]


def test_records_without_a_time_go_last() -> None:
    from sera_ig.models import sort_by_recency

    records = [
        {"name": "none"},
        {"name": "some", "last_activity_at": "2026-05-01T10:00:00+00:00"},
    ]
    assert [r["name"] for r in sort_by_recency(records)] == ["some", "none"]


# ------------------------------------------------------------------- viewer
async def test_the_story_viewer_opens(app) -> None:
    from sera_ig.app.story import StoryScreen

    record = {
        "user": {"username": "noor"},
        "stories": [
            {"pk": "1", "kind": "photo", "taken_at": "2026-05-01T10:00:00+00:00",
             "thumbnail_url": None},
            {"pk": "2", "kind": "photo", "taken_at": "2026-05-01T11:00:00+00:00",
             "thumbnail_url": None},
        ],
    }
    async with app.run_test() as pilot:
        app.show_story(record)
        await pilot.pause()
        assert isinstance(app.screen, StoryScreen)
        assert app.screen.index == 0

        await pilot.press("right")
        await pilot.pause()
        assert app.screen.index == 1

        await pilot.press("left")
        await pilot.pause()
        assert app.screen.index == 0

        await pilot.press("escape")
        await pilot.pause()
