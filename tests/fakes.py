"""A fake instagrapi client.

The fake returns *real* instagrapi model objects (DirectThread, DirectMessage,
Media, …) so the normalisation code is exercised against the same types the
real library produces.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from instagrapi.types import (
    DirectMessage,
    DirectThread,
    Media,
    Story,
    User,
    UserShort,
)

NOW = datetime(2026, 5, 1, 12, 0, 0, tzinfo=timezone.utc)


def make_user(username: str, pk: str | None = None, full_name: str = "") -> UserShort:
    return UserShort(
        pk=pk or f"pk-{username}",
        username=username,
        full_name=full_name or username.title(),
        is_private=False,
        is_verified=False,
    )


def make_message(
    message_id: str,
    text: str = "",
    *,
    user_id: str = "pk-other",
    sent_by_viewer: bool = False,
    minutes_ago: int = 5,
    item_type: str = "text",
) -> DirectMessage:
    return DirectMessage(
        id=message_id,
        thread_id=340282366841510300949128268610842297468,
        timestamp=NOW - timedelta(minutes=minutes_ago),
        item_type=item_type,
        is_sent_by_viewer=sent_by_viewer,
        user_id=user_id,
        text=text,
    )


def make_thread(
    thread_id: str = "340282366841510300949128268610842297468",
    title: str = "",
    usernames: list[str] | None = None,
    messages: list[DirectMessage] | None = None,
    minutes_ago: int = 3,
) -> DirectThread:
    usernames = usernames if usernames is not None else ["noor"]
    users = [make_user(name) for name in usernames]
    return DirectThread(
        pk=f"pk-{thread_id}",
        id=thread_id,
        messages=messages if messages is not None else [],
        users=users,
        admin_user_ids=[users[0].pk],
        last_activity_at=NOW - timedelta(minutes=minutes_ago),
        muted=False,
        named=bool(title),
        canonical=False,
        pending=False,
        archived=False,
        thread_type="private",
        thread_title=title,
        folder=0,
        vc_muted=False,
        is_group=len(users) > 1,
        mentions_muted=False,
        approval_required_for_new_members=False,
        input_mode=0,
    )


def make_media(
    pk: str = "3000000000000000001",
    code: str = "ABC123",
    username: str = "noor",
    caption: str = "hello world",
    media_type: int = 1,
    product_type: str | None = None,
) -> Media:
    if product_type is None:
        product_type = "clips" if media_type == 2 else "feed"
    return Media(
        pk=pk,
        id=f"{pk}_1",
        code=code,
        taken_at=NOW,
        media_type=media_type,
        user=make_user(username),
        like_count=42,
        comment_count=7,
        caption_text=caption,
        usertags=[],
        sponsor_tags=[],
        product_type=product_type,
    )


RAW_MEDIA = {
    "pk": "3000000000000000001",
    "id": "3000000000000000001_99",
    "code": "ABC123",
    "taken_at": 1777636800,
    "media_type": 1,
    "user": {"pk": "99", "username": "noor", "full_name": "Noor"},
    "like_count": 42,
    "comment_count": 7,
    "caption": {"text": "hello world"},
    "image_versions2": {
        "candidates": [
            {"url": "https://cdn.example/1.jpg", "width": 640, "height": 640},
            {"url": "https://cdn.example/1-big.jpg", "width": 1080, "height": 1080},
        ]
    },
}


class FakePrivate:
    """Stands in for ``client.private`` (the requests session)."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}

    def get(self, url: str, **kwargs: Any) -> Any:
        class Response:
            status_code = 200

            def raise_for_status(self) -> None:
                return None

            content = b"binary-data"

        return Response()


class FakeClient:
    """A minimal but faithful stand-in for ``instagrapi.Client``."""

    def __init__(self) -> None:
        self.username = "noor"
        self.user_id = 12345
        self.private = FakePrivate()
        self.sent: list[dict[str, Any]] = []
        self.reactions: list[dict[str, Any]] = []
        self.unsent: list[dict[str, Any]] = []
        self.seen_threads: list[int] = []
        self.threads = [
            make_thread(
                thread_id="340282366841510300949128268610842297468",
                usernames=["noor"],
                messages=[make_message("9001", "hey there", minutes_ago=2)],
            ),
            make_thread(
                thread_id="340282366841510300949128268610842297469",
                title="Weekend plans",
                usernames=["sara", "omar"],
                messages=[
                    make_message("9002", "saturday?", user_id="pk-sara", minutes_ago=30),
                    make_message("9003", "works for me", user_id="pk-omar", minutes_ago=20),
                ],
                minutes_ago=20,
            ),
            make_thread(
                thread_id="340282366841510300949128268610842297470",
                usernames=["noor", "mina"],
                messages=[make_message("9004", "ping", user_id="pk-mina", minutes_ago=120)],
                minutes_ago=120,
            ),
        ]
        self.media = make_media()
        self._settings: dict[str, Any] = {"uuids": {"uuid": "x"}}

    # ------------------------------------------------------------- sessions
    def get_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    def set_settings(self, settings: dict[str, Any]) -> bool:
        self._settings = dict(settings)
        return True

    def account_info(self) -> User:
        return User(
            pk="12345",
            username="noor",
            full_name="Noor",
            is_private=False,
            profile_pic_url="https://cdn.example/pic.jpg",
            is_verified=False,
            media_count=10,
            follower_count=100,
            following_count=50,
            biography="hello",
            is_business=False,
        )

    # --------------------------------------------------------------- direct
    def direct_threads(
        self,
        amount: int = 20,
        selected_filter: Any = None,
        box: Any = None,
        thread_message_limit: int | None = None,
    ) -> list[DirectThread]:
        threads = list(self.threads[:amount])
        if thread_message_limit is not None:
            for thread in threads:
                thread.messages = thread.messages[-thread_message_limit:]
        return threads

    def direct_thread(self, thread_id: int, amount: int = 20) -> DirectThread:
        for thread in self.threads:
            if str(thread.id) == str(thread_id):
                return thread
        raise ValueError("thread not found")

    def direct_messages(self, thread_id: int, amount: int = 20) -> list[DirectMessage]:
        thread = self.direct_thread(thread_id)
        return list(thread.messages)[:amount]

    def direct_message(self, thread_id: int, message_id: int, amount: int = 20) -> DirectMessage:
        for message in self.direct_messages(thread_id, amount=50):
            if str(message.id) == str(message_id):
                return message
        raise ValueError("message not found")

    def direct_send(
        self,
        text: str,
        user_ids: list[int] | None = None,
        thread_ids: list[int] | None = None,
        send_attribute: str = "message_button",
        reply_to_message: DirectMessage | None = None,
    ) -> DirectMessage:
        self.sent.append(
            {
                "text": text,
                "thread_ids": thread_ids or [],
                "reply_to": reply_to_message.id if reply_to_message else None,
            }
        )
        return make_message("9999", text, sent_by_viewer=True, minutes_ago=0)

    def direct_send_photo(self, path: Path, user_ids: list[int] | None = None, thread_ids: list[int] | None = None) -> DirectMessage:
        self.sent.append({"photo": str(path), "thread_ids": thread_ids or []})
        return make_message("9998", "", sent_by_viewer=True, minutes_ago=0, item_type="media")

    def direct_send_video(self, path: Path, user_ids: list[int] | None = None, thread_ids: list[int] | None = None) -> DirectMessage:
        self.sent.append({"video": str(path), "thread_ids": thread_ids or []})
        return make_message("9997", "", sent_by_viewer=True, minutes_ago=0, item_type="media")

    def direct_send_reaction(self, thread_id: int, message_id: int, emoji: str = "❤", **kwargs: Any) -> bool:
        self.reactions.append({"thread_id": thread_id, "message_id": message_id, "emoji": emoji})
        return True

    def direct_message_unsend(self, thread_id: int, message_id: int) -> bool:
        self.unsent.append({"thread_id": thread_id, "message_id": message_id})
        return True

    def direct_send_seen(self, thread_id: int) -> bool:
        self.seen_threads.append(thread_id)
        return True

    def direct_search(self, query: str, mode: str = "universal") -> list[UserShort]:
        return [
            make_user("noor", pk="1", full_name="Noor H"),
            make_user("noorhan", pk="2", full_name="Noor Hamid"),
        ]

    def direct_thread_by_participants(self, user_ids: list[int]) -> dict[str, Any]:
        new_id = "340282366841510300949128268610842297471"
        self.threads.append(
            make_thread(thread_id=new_id, usernames=["brandnewperson"], minutes_ago=0)
        )
        return {"thread_id": new_id, "status": "ok"}

    # ------------------------------------------------------------------ feed
    def get_timeline_feed(self, reason: str = "pull_to_refresh", max_id: str = None) -> dict[str, Any]:
        return {"feed_items": [{"media_or_ad": dict(RAW_MEDIA)}], "num_results": 1}

    def reels(self, amount: int = 10, last_media_pk: int = 0) -> list[Media]:
        return [make_media(pk="3000000000000000002", code="REEL1", media_type=2)]

    def explore_reels(self, amount: int = 10, last_media_pk: int = 0) -> list[Media]:
        return [make_media(pk="3000000000000000003", code="EXPL1", media_type=2)]

    # --------------------------------------------------------------- stories
    def get_reels_tray_feed(self, reason: str = "cold_start") -> dict[str, Any]:
        return {
            "tray": [
                {
                    "user": {"pk": "99", "username": "noor", "full_name": "Noor"},
                    "items": [
                        {
                            "pk": "5001",
                            "id": "5001_99",
                            "code": "STORY1",
                            "taken_at": 1777636800,
                            "media_type": 1,
                            "image_versions2": {
                                "candidates": [
                                    {"url": "https://cdn.example/s.jpg", "width": 1080, "height": 1920}
                                ]
                            },
                        }
                    ],
                }
            ]
        }

    def user_stories(self, user_id: str, amount: int | None = None) -> list[Story]:
        return [
            Story(
                pk="6001",
                id="6001_99",
                code="STORY2",
                taken_at=NOW,
                media_type=1,
                user=make_user("noor", pk="99"),
                sponsor_tags=[],
                mentions=[],
                links=[],
                hashtags=[],
                locations=[],
                stickers=[],
            )
        ]

    # --------------------------------------------------------- notifications
    def news_inbox_v1(self, mark_as_seen: bool = False) -> dict[str, Any]:
        return {
            "items": [
                {
                    "type": 1,
                    "args": {
                        "text": "liked your post",
                        "timestamp": 1777636800,
                        "media": {"pk": "1", "code": "ABC123", "thumbnail_url": "https://cdn.example/t.jpg"},
                    },
                    "story": {"pk": "99", "username": "sara", "full_name": "Sara"},
                }
            ],
            "counts": {"like": 1},
        }

    # ------------------------------------------------------------------ user
    def user_info_by_username(self, username: str, use_cache: bool = True) -> User:
        return User(
            pk="99",
            username=username,
            full_name=username.title(),
            is_private=False,
            profile_pic_url="https://cdn.example/pic.jpg",
            is_verified=True,
            media_count=12,
            follower_count=345,
            following_count=67,
            biography="bio text",
            is_business=False,
        )

    def user_info(self, user_id: str, use_cache: bool = True) -> User:
        """instagrapi's user_info takes an id, not a username."""
        return self.user_info_by_username(str(user_id))

    def user_medias(self, user_id: str, amount: int = 0, sleep: int = 0) -> list[Media]:
        return [make_media()]

    def user_followers(self, user_id: str, use_cache: bool = True, amount: int = 0) -> list[UserShort]:
        return [make_user("fan1", pk="f1")]

    def user_following(self, user_id: str, use_cache: bool = True, amount: int = 0) -> dict[str, UserShort]:
        return {"f1": make_user("followed", pk="f2")}

    # ----------------------------------------------------------------- media
    def media_info(self, media_pk: str, use_cache: bool = True) -> Media:
        return self.media

    def media_pk_from_url(self, url: str) -> str:
        if "ABC123" in url:
            return "3000000000000000001"
        raise ValueError("unknown url")

    def media_like(self, media_id: str, revert: bool = False) -> bool:
        return True

    def media_comment(self, media_id: str, text: str, replied_to_comment_id: int | None = None) -> Any:
        return SimpleNamespace(
            pk="c1",
            text=text,
            user=make_user("noor", pk="99"),
            created_at_utc=NOW,
            like_count=0,
        )

    def media_comments(self, media_id: str, amount: int = 20) -> list[Any]:
        return [
            SimpleNamespace(
                pk="c1",
                text="nice shot",
                user=make_user("sara", pk="88"),
                created_at_utc=NOW,
                like_count=3,
            )
        ]

    def photo_download(self, media_pk: str, folder: Path = "", overwrite: bool = True) -> Path:
        target = Path(folder or "/tmp") / f"{media_pk}.jpg"
        target.write_bytes(b"jpeg")
        return target

    def video_download(self, media_pk: str, folder: Path = "", overwrite: bool = True) -> Path:
        target = Path(folder or "/tmp") / f"{media_pk}.mp4"
        target.write_bytes(b"mp4")
        return target
