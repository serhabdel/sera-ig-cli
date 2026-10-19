"""Normalisation of instagrapi objects into plain, JSON-friendly dicts.

The instagrapi models are pydantic objects with a lot of fields Instagram
does not need. These helpers project them down to the handful of fields the
CLI (and any agent consuming its JSON output) actually uses.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from instagrapi.types import DirectMessage, DirectThread, Media, Story, UserShort


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _first_url(candidates: Any) -> str | None:
    """Pick the best URL out of an ``image_versions2`` style structure."""
    if not candidates:
        return None
    if isinstance(candidates, dict):
        candidates = candidates.get("candidates") or []
    for candidate in candidates or []:
        url = getattr(candidate, "url", None) or (
            candidate.get("url") if isinstance(candidate, dict) else None
        )
        width = getattr(candidate, "width", None) or (
            candidate.get("width") if isinstance(candidate, dict) else None
        )
        if url and (width is None or width >= 640):
            return str(url)
    for candidate in candidates or []:
        url = getattr(candidate, "url", None) or (
            candidate.get("url") if isinstance(candidate, dict) else None
        )
        if url:
            return str(url)
    return None


def user_to_dict(user: UserShort | None) -> dict[str, Any]:
    """Project a user down to the fields the CLI exposes."""
    if user is None:
        return {}
    return {
        "pk": str(user.pk),
        "username": user.username,
        "full_name": user.full_name or "",
        "is_private": bool(user.is_private),
        "is_verified": bool(user.is_verified),
        "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None,
    }


def thread_to_dict(thread: DirectThread, *, last_message: DirectMessage | None = None) -> dict[str, Any]:
    """Project a DM thread into a flat dict."""
    users = [user_to_dict(user) for user in thread.users]
    usernames = [u["username"] for u in users if u.get("username")]
    message = last_message if last_message is not None else (thread.messages[-1] if thread.messages else None)
    return {
        "id": str(thread.id),
        "pk": str(thread.pk),
        "title": thread.thread_title or (usernames[0] if usernames else ""),
        "named": bool(thread.named),
        "is_group": bool(thread.is_group),
        "pending": bool(thread.pending),
        "muted": bool(thread.muted),
        "users": users,
        "usernames": usernames,
        "last_activity_at": _iso(thread.last_activity_at),
        "message_count": len(thread.messages),
        "last_message": message_to_dict(message) if message else None,
    }


def _message_kind(message: DirectMessage) -> str:
    """Classify a direct message by what it carries."""
    item_type = (message.item_type or "").lower()
    if item_type:
        if item_type in {"text", "text_mention"}:
            return "text"
        return item_type
    if message.text:
        return "text"
    if message.media:
        return "media"
    if message.media_share:
        return "media_share"
    if message.clip:
        return "reel"
    if message.reel_share:
        return "reel_share"
    if message.story_share:
        return "story_share"
    if message.xma_share:
        return "xma_share"
    if message.visual_media:
        return "visual_media"
    if message.link:
        return "link"
    return "unknown"


def message_to_dict(message: DirectMessage | None) -> dict[str, Any]:
    """Project a direct message into a flat dict."""
    if message is None:
        return {}

    text = message.text
    media: dict[str, Any] | None = None
    media_pk: str | None = None
    media_url: str | None = None

    if message.media:
        media_url = str(message.media.video_url or message.media.thumbnail_url) if (
            message.media.video_url or message.media.thumbnail_url
        ) else None
        media = {
            "type": message.media.media_type,
            "url": media_url,
        }
    elif message.media_share:
        media_pk = str(message.media_share.pk)
        media_url = media_thumbnail(message.media_share)
        media = {
            "type": message.media_share.media_type,
            "pk": media_pk,
            "code": message.media_share.code,
            "url": media_url,
            "owner": user_to_dict(message.media_share.user),
            "caption": (message.media_share.caption_text or "")[:300],
        }
    elif message.clip:
        media_pk = str(message.clip.pk)
        media_url = str(message.clip.video_url) if message.clip.video_url else None
        media = {
            "type": message.clip.media_type,
            "pk": media_pk,
            "code": message.clip.code,
            "url": media_url,
            "owner": user_to_dict(message.clip.user),
            "caption": (message.clip.caption_text or "")[:300],
        }
    elif message.visual_media:
        media = {"type": "visual_media"}
        text = text or "[visual media]"

    reactions = []
    if message.reactions and message.reactions.emojis:
        for reaction in message.reactions.emojis:
            reactions.append(
                {
                    "emoji": reaction.emoji,
                    "sender_id": str(reaction.sender_id),
                    "timestamp": _iso(reaction.timestamp),
                }
            )

    return {
        "id": str(message.id),
        "thread_id": str(message.thread_id) if message.thread_id else None,
        "timestamp": _iso(message.timestamp),
        "kind": _message_kind(message),
        "text": text or "",
        "is_sent_by_viewer": bool(message.is_sent_by_viewer),
        "user_id": str(message.user_id) if message.user_id else None,
        "media": media,
        "media_pk": media_pk,
        "media_url": media_url,
        "reactions": reactions,
    }


def media_thumbnail(media: Media | None) -> str | None:
    """Best available thumbnail URL for a media object."""
    if media is None:
        return None
    if media.image_versions2:
        url = _first_url(media.image_versions2)
        if url:
            return url
    if media.thumbnail_url:
        return str(media.thumbnail_url)
    return None


def media_to_dict(media: Media | None) -> dict[str, Any]:
    """Project a feed media into a flat dict."""
    if media is None:
        return {}
    return {
        "pk": str(media.pk),
        "id": str(media.id),
        "code": media.code,
        "url": f"https://www.instagram.com/p/{media.code}/",
        "media_type": media.media_type,
        "kind": _media_kind(media),
        "taken_at": _iso(media.taken_at),
        "user": user_to_dict(media.user),
        "caption": media.caption_text or "",
        "like_count": media.like_count,
        "comment_count": media.comment_count,
        "has_liked": bool(media.has_liked),
        "thumbnail_url": media_thumbnail(media),
        "video_url": str(media.video_url) if media.video_url else None,
        "view_count": media.view_count,
    }


def _media_kind(media: Media) -> str:
    product = (media.product_type or "").lower()
    if product == "clips":
        return "reel"
    if product == "igtv":
        return "igtv"
    if product == "feed":
        return "post"
    return {1: "photo", 2: "video", 8: "album"}.get(media.media_type, "media")


def story_to_dict(story: Story | None) -> dict[str, Any]:
    """Project a story into a flat dict."""
    if story is None:
        return {}
    return {
        "pk": str(story.pk),
        "id": str(story.id),
        "taken_at": _iso(story.taken_at),
        "media_type": story.media_type,
        "kind": "video" if story.media_type == 2 else "photo",
        "user": user_to_dict(story.user),
        "thumbnail_url": str(story.thumbnail_url) if story.thumbnail_url else None,
        "video_url": str(story.video_url) if story.video_url else None,
        "video_duration": story.video_duration,
        "mentions": [user_to_dict(m.user) for m in (story.mentions or [])],
        "polls": [
            {"question": poll.question, "options": [opt.text for opt in (poll.options or [])]}
            for poll in (story.polls or [])
        ],
    }
