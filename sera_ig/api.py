"""The data layer.

Thin, well-named functions around instagrapi that return plain dicts. The
command modules only deal with argument parsing and presentation; everything
that talks to Instagram lives here, which keeps the surface easy to test and
easy to swap.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from instagrapi.extractors import extract_media_v1
from instagrapi.types import DirectThread

from .errors import NotFoundError, UsageError
from .models import (
    media_thumbnail,
    media_to_dict,
    message_to_dict,
    story_to_dict,
    thread_to_dict,
    user_to_dict,
)
from .resolve import looks_like_thread_id, resolve_thread

#: How many messages are fetched when a reply has to find its target.
REPLY_LOOKUP_LIMIT = 20

# --------------------------------------------------------------------- threads


def list_threads(
    client: Any,
    *,
    amount: int = 20,
    selected_filter: str | None = None,
    search: str | None = None,
    message_limit: int | None = None,
) -> list[dict[str, Any]]:
    """Return the DM inbox as a list of normalised thread dicts.

    Instagram's inbox endpoint paginates, and every page is another round
    trip, so *amount* decides how many requests this makes. *message_limit*
    caps how many messages come back with each thread — the inbox only needs
    the last one, and the full history makes the payload much heavier.
    """
    threads = client.direct_threads(
        amount=amount,
        selected_filter=selected_filter if selected_filter in (None, "", "all") else selected_filter,
        thread_message_limit=message_limit,
    )
    records = []
    for thread in threads:
        record = thread_to_dict(thread)
        if search:
            needle = search.lower().lstrip("@")
            haystack = " ".join(
                [record["title"], *record["usernames"]]
            ).lower()
            if needle not in haystack:
                continue
        records.append(record)
    records.sort(key=lambda item: item.get("last_activity_at") or "", reverse=True)
    return records


def get_thread(client: Any, reference: str, *, create: bool = False) -> DirectThread:
    """Resolve *reference* to a thread object."""
    return resolve_thread(client, reference, create=create)


def open_thread(
    client: Any,
    thread_id: str | int,
    *,
    message_limit: int = 50,
) -> tuple[DirectThread, list[dict[str, Any]]]:
    """Fetch a thread **and** its messages in a single request.

    ``direct_thread`` returns the conversation together with its most recent
    messages, so opening a conversation costs one round trip instead of
    listing the whole inbox and then asking for the thread again.
    """
    thread = client.direct_thread(int(thread_id), amount=message_limit)
    records = [message_to_dict(message) for message in thread.messages]
    records.sort(key=lambda item: item.get("timestamp") or "")
    return thread, records


def read_messages(client: Any, thread: DirectThread, *, limit: int = 20) -> list[dict[str, Any]]:
    """Return the last *limit* messages of *thread* as normalised dicts.

    Messages are ordered oldest first, which is how a conversation reads
    naturally. Instagram returns them newest first, so they are sorted here
    rather than relying on the API order.
    """
    messages = client.direct_messages(int(thread.id), amount=limit)
    records = [message_to_dict(message) for message in messages]
    records.sort(key=lambda item: item.get("timestamp") or "")
    return records


def read_conversation(
    client: Any,
    reference: str,
    *,
    limit: int = 50,
    create: bool = False,
) -> tuple[DirectThread, list[dict[str, Any]]]:
    """Fetch a conversation and its messages in as few requests as possible.

    A thread id is fetched straight away, with its messages in the same round
    trip. A name has to be looked up first, which costs one more request.
    """
    if looks_like_thread_id(reference):
        return open_thread(client, reference, message_limit=limit)
    thread = get_thread(client, reference, create=create)
    return thread, read_messages(client, thread, limit=limit)


def send_text(
    client: Any,
    thread: DirectThread,
    text: str,
    *,
    reply_to: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a text message to *thread*, optionally as a reply."""
    reply_message = None
    if reply_to:
        try:
            # The message has to be among the ones the endpoint returns, so
            # ask for a page of them rather than only the newest.
            reply_message = client.direct_message(
                int(thread.id), int(reply_to["id"]), amount=REPLY_LOOKUP_LIMIT
            )
        except Exception as exc:
            raise NotFoundError(
                f"Message {reply_to.get('id')} was not found in this thread."
            ) from exc

    message = client.direct_send(
        text,
        thread_ids=[int(thread.id)],
        reply_to_message=reply_message,
    )
    return message_to_dict(message)


def send_media(client: Any, thread: DirectThread, path: Path) -> dict[str, Any]:
    """Send a photo or video to *thread*."""
    path = path.expanduser().resolve()
    if not path.exists():
        raise UsageError(f"No such file: {path}")

    guessed = mimetypes.guess_type(path.name)[0] or ""
    is_video = guessed.startswith("video/") or path.suffix.lower() in {
        ".mp4",
        ".mov",
        ".m4v",
        ".webm",
        ".avi",
    }
    if is_video:
        message = client.direct_send_video(path, thread_ids=[int(thread.id)])
    else:
        message = client.direct_send_photo(path, thread_ids=[int(thread.id)])
    return message_to_dict(message)


def react(client: Any, thread: DirectThread, message_id: str, emoji: str) -> bool:
    """React to a message with *emoji*."""
    client.direct_send_reaction(int(thread.id), int(message_id), emoji=emoji)
    return True


def unsend(client: Any, thread: DirectThread, message_id: str) -> bool:
    """Delete (unsend) a message you sent."""
    return bool(client.direct_message_unsend(int(thread.id), int(message_id)))


def mark_seen(client: Any, thread: DirectThread) -> bool:
    """Mark a thread as read."""
    return bool(client.direct_send_seen(int(thread.id)))


def search_users(client: Any, query: str) -> list[dict[str, Any]]:
    """Search Instagram for users matching *query*."""
    users = client.direct_search(query)
    return [user_to_dict(user) for user in users]


# ----------------------------------------------------------------------- feed


def timeline(client: Any, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return the home timeline as normalised media dicts."""
    response = client.get_timeline_feed()
    records: list[dict[str, Any]] = []
    for item in response.get("feed_items") or response.get("items") or []:
        if not isinstance(item, dict):
            continue
        raw = item.get("media_or_ad") or item.get("media")
        if not isinstance(raw, dict):
            continue
        try:
            media = extract_media_v1(raw)
        except Exception:  # pragma: no cover - malformed feed item
            continue
        records.append(media_to_dict(media))
        if len(records) >= amount:
            break
    return records


def reels(client: Any, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return reels from the connected-reels tray."""
    return [media_to_dict(media) for media in client.reels(amount=amount)]


def explore_reels(client: Any, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return reels from the explore tab."""
    return [media_to_dict(media) for media in client.explore_reels(amount=amount)]


# -------------------------------------------------------------------- stories


def stories_tray(
    client: Any,
    user_ids: list[str] | None = None,
    *,
    keys: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Return the stories tray (people you follow who have active stories).

    The tray endpoint is asked first. When it comes back empty — Instagram
    moves this payload around, and it sometimes answers with something else —
    the people you have conversations with are asked directly, which is the
    same thing the tray shows.
    """
    records = _stories_from_reels_tray(client, keys)
    if records:
        return records
    return _stories_from_users(client, user_ids or [])


def stories_raw_keys(client: Any) -> list[str]:
    """Return the top level keys of the tray response.

    Useful when the tray is empty and it is not clear why.
    """
    try:
        response = client.get_reels_tray_feed("cold_start")
    except Exception as exc:
        return [f"error: {exc}"]
    if isinstance(response, dict):
        return sorted(response)
    return [f"unexpected response: {type(response).__name__}"]


def _stories_from_reels_tray(
    client: Any, keys: list[str] | None = None
) -> list[dict[str, Any]]:
    """Read the stories out of the reels tray response."""
    try:
        response = client.get_reels_tray_feed("cold_start")
    except Exception as exc:
        if keys is not None:
            keys.append(f"error: {exc}")
        return []

    if not isinstance(response, dict):
        if keys is not None:
            keys.append(f"unexpected response: {type(response).__name__}")
        return []
    if keys is not None:
        keys.extend(sorted(response))

    tray = response.get("tray") or response.get("stories") or []
    if isinstance(tray, dict):
        tray = list(tray.values())
    if not isinstance(tray, list):
        return []

    records: list[dict[str, Any]] = []
    for entry in tray:
        if not isinstance(entry, dict):
            continue
        user = entry.get("user") or {}
        items = entry.get("items") or entry.get("media") or []
        if not isinstance(items, list):
            continue
        stories = []
        for story in items:
            try:
                stories.append(story_to_dict(_build_story(story, user)))
            except Exception:  # pragma: no cover - malformed story
                continue
        if not stories:
            continue
        records.append(
            {
                "user": {
                    "pk": str(user.get("pk") or ""),
                    "username": user.get("username"),
                    "full_name": user.get("full_name") or "",
                    "is_private": bool(user.get("is_private")),
                    "is_verified": bool(user.get("is_verified")),
                    "profile_pic_url": user.get("profile_pic_url"),
                },
                "story_count": len(stories),
                "stories": stories,
            }
        )
    return records


def _stories_from_users(client: Any, user_ids: list[str]) -> list[dict[str, Any]]:
    """Ask the given users directly whether they have stories.

    This is the same GraphQL call the tray is built on, done for a known
    list of people, so it still works when the tray endpoint does not.
    """
    wanted = [str(uid) for uid in user_ids if uid][:50]
    if not wanted:
        return []

    try:
        users = client.users_stories_gql([int(uid) for uid in wanted])
    except Exception:
        return []

    records: list[dict[str, Any]] = []
    for user in users or []:
        stories = getattr(user, "stories", None) or []
        if not stories:
            continue
        records.append(
            {
                "user": {
                    "pk": str(user.pk),
                    "username": user.username,
                    "full_name": user.full_name or "",
                    "is_private": bool(user.is_private),
                    "is_verified": bool(user.is_verified),
                    "profile_pic_url": (
                        str(user.profile_pic_url) if user.profile_pic_url else None
                    ),
                },
                "story_count": len(stories),
                "stories": [story_to_dict(story) for story in stories],
            }
        )
    return records


def conversation_user_ids(client: Any, amount: int = 20) -> list[str]:
    """Return the ids of the people you have conversations with."""
    try:
        threads = client.direct_threads(amount=amount, thread_message_limit=1)
    except Exception:
        return []
    ids: list[str] = []
    for thread in threads or []:
        for user in thread.users:
            if user.pk and str(user.pk) not in ids:
                ids.append(str(user.pk))
    return ids


def _build_story(raw: dict[str, Any], user: dict[str, Any]) -> Any:
    """Build a :class:`instagrapi.types.Story` from a raw tray item."""
    from instagrapi.types import Story, UserShort

    user_short = UserShort(
        pk=str(user.get("pk") or raw.get("user", {}).get("pk") or "0"),
        username=user.get("username"),
        full_name=user.get("full_name") or "",
        is_private=bool(user.get("is_private")),
        is_verified=bool(user.get("is_verified")),
        profile_pic_url=user.get("profile_pic_url"),
    )
    thumbnail = raw.get("thumbnail_url")
    if not thumbnail:
        thumbnail = _first_candidate_url(raw.get("image_versions2"))
    return Story(
        pk=str(raw.get("pk") or raw.get("id") or "0"),
        id=str(raw.get("id") or raw.get("pk") or "0"),
        code=str(raw.get("code") or ""),
        taken_at=raw.get("taken_at"),
        media_type=raw.get("media_type", 1),
        thumbnail_url=thumbnail,
        user=user_short,
        video_url=raw.get("video_url"),
        video_duration=raw.get("video_duration", 0.0),
        sponsor_tags=[],
        mentions=[],
        links=[],
        hashtags=[],
        locations=[],
        stickers=[],
        polls=[],
    )


def _first_candidate_url(image_versions: Any) -> str | None:
    """Return the largest candidate URL of an ``image_versions2`` block."""
    if not image_versions:
        return None
    if isinstance(image_versions, dict):
        candidates = image_versions.get("candidates") or []
    else:
        candidates = image_versions
    best: tuple[int, str] | None = None
    for candidate in candidates:
        url = candidate.get("url") if isinstance(candidate, dict) else getattr(candidate, "url", None)
        if not url:
            continue
        size = candidate.get("width", 0) if isinstance(candidate, dict) else getattr(candidate, "width", 0)
        if best is None or (size or 0) > best[0]:
            best = (size or 0, str(url))
    return best[1] if best else None


def user_stories(client: Any, username: str) -> list[dict[str, Any]]:
    """Return the active stories of a single user."""
    user = _user_info(client, username)
    stories = client.user_stories(str(user.pk))
    return [story_to_dict(story) for story in stories]


# -------------------------------------------------------------- notifications


def notifications(client: Any, *, limit: int = 20) -> list[dict[str, Any]]:
    """Return the activity feed (likes, comments, follows …)."""
    response = client.news_inbox_v1(mark_as_seen=False)
    records: list[dict[str, Any]] = []
    for item in response.get("items") or []:
        if not isinstance(item, dict):
            continue
        args = item.get("args") or {}
        story = item.get("story") or {}
        media = args.get("media") or {}
        records.append(
            {
                "type": _activity_label(item.get("type")),
                "timestamp": args.get("timestamp"),
                "text": args.get("text") or "",
                "profile_pic_url": story.get("profile_pic_url"),
                "user": {
                    "pk": str(story.get("pk") or ""),
                    "username": story.get("username"),
                    "full_name": story.get("full_name") or "",
                },
                "media": {
                    "pk": str(media.get("pk") or ""),
                    "code": media.get("code"),
                    "url": f"https://www.instagram.com/p/{media.get('code')}/"
                    if media.get("code")
                    else None,
                    "thumbnail_url": media.get("thumbnail_url"),
                }
                if media
                else None,
            }
        )
        if len(records) >= limit:
            break
    return records


def _activity_label(kind: Any) -> str:
    """Map the numeric activity type onto a label."""
    try:
        kind = int(kind)
    except (TypeError, ValueError):
        return str(kind or "activity")
    return {
        1: "like",
        2: "comment",
        3: "follow",
        4: "request",
        5: "hashtag_comment",
        6: "like_and_comment_on_media_user_tagged",
        7: "user_tagged",
        8: "comment_like",
        9: "first_post",
        10: "comment_on_media_user_tagged",
        12: "connection",
        14: "video_view",
        15: "direct_share",
    }.get(kind, f"activity_{kind}")


# ----------------------------------------------------------------------- user


def _user_info(client: Any, username: str) -> Any:
    """Look up a user, turning a failed lookup into a clear message."""
    from instagrapi.exceptions import ClientGraphqlError

    try:
        return client.user_info_by_username(username)
    except (NotFoundError, ClientGraphqlError) as exc:
        raise NotFoundError(
            f"No Instagram account named '{username}'. "
            "Check the spelling, or search for it with `seraig search`."
        ) from exc
    except Exception as exc:
        if type(exc).__name__ in ("UserNotFound", "ClientNotFoundError"):
            raise NotFoundError(
                f"No Instagram account named '{username}'. "
                "Check the spelling, or search for it with `seraig search`."
            ) from exc
        raise


def user_profile(client: Any, username: str) -> dict[str, Any]:
    """Return a profile summary for *username*."""
    user = _user_info(client, username)
    return {
        "pk": str(user.pk),
        "username": user.username,
        "full_name": user.full_name,
        "is_private": bool(user.is_private),
        "is_verified": bool(user.is_verified),
        "followers": user.follower_count,
        "following": user.following_count,
        "posts": user.media_count,
        "biography": user.biography or "",
        "external_url": str(user.external_url) if user.external_url else None,
        "profile_pic_url": str(user.profile_pic_url) if user.profile_pic_url else None,
        "url": f"https://www.instagram.com/{user.username}/",
    }


def user_posts(client: Any, username: str, *, amount: int = 12) -> list[dict[str, Any]]:
    """Return the latest posts of *username*."""
    user = _user_info(client, username)
    medias = client.user_medias(str(user.pk), amount=amount)
    return [media_to_dict(media) for media in medias]


def user_followers(client: Any, username: str, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return the followers of *username*."""
    user = _user_info(client, username)
    followers = client.user_followers(str(user.pk), amount=amount)
    return [user_to_dict(follower) for follower in followers]


def user_following(client: Any, username: str, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return the accounts *username* follows."""
    user = _user_info(client, username)
    following = client.user_following(str(user.pk), amount=amount)
    return [user_to_dict(entry) for entry in following.values()]


# ---------------------------------------------------------------------- media


def resolve_media_pk(client: Any, reference: str) -> str:
    """Accept a media id, a short code or a full URL and return the media pk."""
    reference = (reference or "").strip()
    if not reference:
        raise UsageError("No media reference given.")
    if reference.isdigit():
        return reference
    if reference.startswith("http") or "/" in reference:
        try:
            return str(client.media_pk_from_url(reference))
        except Exception as exc:
            raise NotFoundError(f"Could not read a media id from '{reference}'.") from exc
    # A short code such as "ABC123" or "B1c2D3e4F5g".
    try:
        return str(client.media_pk_from_url(f"https://www.instagram.com/p/{reference}/"))
    except Exception as exc:
        raise NotFoundError(
            f"'{reference}' is not a media id or URL. Use a numeric id, a short code, or a post URL."
        ) from exc


def media_info(client: Any, reference: str) -> dict[str, Any]:
    """Return the details of a single media."""
    pk = resolve_media_pk(client, reference)
    try:
        media = client.media_info(pk)
    except Exception as exc:
        raise NotFoundError(f"Could not load media {pk}.") from exc
    record = media_to_dict(media)
    record["thumbnail_url"] = media_thumbnail(media)
    return record


def like_media(client: Any, reference: str, *, revert: bool = False) -> bool:
    """Like (or unlike) a media."""
    pk = resolve_media_pk(client, reference)
    return bool(client.media_like(pk, revert=revert))


def comment_media(client: Any, reference: str, text: str) -> dict[str, Any]:
    """Post a comment on a media."""
    pk = resolve_media_pk(client, reference)
    comment = client.media_comment(pk, text)
    return {
        "pk": str(comment.pk),
        "text": comment.text,
        "user": user_to_dict(comment.user),
        "created_at": comment.created_at_utc.isoformat() if comment.created_at_utc else None,
    }


def media_comments(client: Any, reference: str, *, amount: int = 20) -> list[dict[str, Any]]:
    """Return the comments of a media."""
    pk = resolve_media_pk(client, reference)
    comments = client.media_comments(pk, amount=amount)
    return [
        {
            "pk": str(comment.pk),
            "text": comment.text,
            "user": user_to_dict(comment.user),
            "created_at": comment.created_at_utc.isoformat() if comment.created_at_utc else None,
            "like_count": comment.like_count,
        }
        for comment in comments
    ]


def download_media(client: Any, reference: str, destination: Path | None = None) -> Path:
    """Download a photo or video to *destination* (a file or a directory)."""
    pk = resolve_media_pk(client, reference)
    try:
        media = client.media_info(pk)
    except Exception as exc:
        raise NotFoundError(f"Could not load media {pk}.") from exc

    if destination is None:
        base = Path.home() / ".sera-ig-cli" / "downloads"
        base.mkdir(parents=True, exist_ok=True)
        destination = base

    destination = destination.expanduser()
    # A destination that names a file gets exactly that name; anything else is
    # treated as a directory to drop the download into.
    looks_like_file = destination.suffix != "" and not destination.is_dir()
    if looks_like_file:
        folder = destination.parent
        folder.mkdir(parents=True, exist_ok=True)
    else:
        folder = destination
        folder.mkdir(parents=True, exist_ok=True)

    if media.media_type == 2:
        saved = Path(client.video_download(pk, folder=folder, overwrite=True))
    elif media.media_type == 1:
        saved = Path(client.photo_download(pk, folder=folder, overwrite=True))
    elif getattr(media, "resources", None):
        resource = media.resources[0]
        if getattr(resource, "media_type", 1) == 2:
            saved = Path(client.video_download(str(resource.pk), folder=folder, overwrite=True))
        else:
            saved = Path(client.photo_download(str(resource.pk), folder=folder, overwrite=True))
    else:
        raise UsageError("This media type cannot be downloaded directly.")

    if looks_like_file and saved != destination:
        saved.replace(destination)
        saved = destination
    return saved


# ------------------------------------------------------------------ searching


def search_messages(client: Any, query: str) -> list[dict[str, Any]]:
    """Search every conversation for *query*.

    This is Instagram's own message search, and it reaches the messages of
    conversations that are not in the inbox any more.
    """
    query = (query or "").strip()
    if not query:
        return []

    records: list[dict[str, Any]] = []
    try:
        results = client.direct_message_search(query)
    except Exception as exc:
        raise NotFoundError(f"The search could not be run: {exc}") from exc

    for message, thread in results or []:
        record = message_to_dict(message)
        record["conversation"] = {
            "id": str(thread.id),
            "title": thread.thread_title
            or " ".join(user.username for user in thread.users if user.username),
            "usernames": [user.username for user in thread.users if user.username],
        }
        records.append(record)
    return records


# ------------------------------------------------------------------- presence


def users_presence(client: Any, user_ids: list[str]) -> dict[str, bool]:
    """Return which of *user_ids* are active right now.

    Instagram answers with a mapping of user id to a presence record; only
    the ones that are active are of interest.
    """
    wanted = [str(uid) for uid in user_ids if uid]
    if not wanted:
        return {}

    try:
        result = client.direct_users_presence([int(uid) for uid in wanted])
    except Exception:
        return {}

    active: dict[str, bool] = {}
    if not isinstance(result, dict):
        return active

    # The shape varies; look for the user id under a few plausible keys.
    for key, value in result.items():
        if not isinstance(value, dict):
            continue
        user = value.get("user") or value
        pk = user.get("pk") or user.get("id") or key
        if pk is None:
            continue
        is_active = bool(
            value.get("is_active")
            or user.get("is_active")
            or value.get("presence_status") == "active"
        )
        active[str(pk)] = is_active
    return active


# ------------------------------------------------------------- message requests


def pending_requests(client: Any, amount: int = 20) -> list[dict[str, Any]]:
    """Return the conversations waiting to be accepted."""
    try:
        threads = client.direct_pending_inbox(amount=amount)
    except Exception:
        return []
    records = [thread_to_dict(thread) for thread in threads or []]
    records.sort(key=lambda item: item.get("last_activity_at") or "", reverse=True)
    return records


# ------------------------------------------------------------------- actions


def mark_message_seen(client: Any, thread_id: str | int, message_id: str) -> bool:
    """Mark one message as seen."""
    try:
        return bool(client.direct_message_seen(int(thread_id), int(message_id)))
    except Exception:
        return False


def like_message(client: Any, thread_id: str | int, message_id: str) -> bool:
    """Put a heart on a message."""
    try:
        return bool(client.direct_message_like(int(thread_id), int(message_id)))
    except Exception:
        return False


def mute_thread(client: Any, thread_id: str | int, *, revert: bool = False) -> bool:
    """Mute a conversation, or unmute it."""
    try:
        return bool(client.direct_thread_mute(int(thread_id), revert=revert))
    except Exception:
        return False


def mark_thread_unread(client: Any, thread_id: str | int) -> bool:
    """Mark a conversation as unread."""
    try:
        return bool(client.direct_thread_mark_unread(int(thread_id)))
    except Exception:
        return False


def rename_thread(client: Any, thread_id: str | int, title: str) -> bool:
    """Give a group conversation a new name."""
    try:
        return bool(client.direct_thread_update_title(int(thread_id), title))
    except Exception:
        return False


def add_to_thread(client: Any, thread_id: str | int, usernames: list[str]) -> bool:
    """Add people to a group conversation."""
    if not usernames:
        return False
    try:
        user_ids = [int(client.user_info_by_username(name).pk) for name in usernames]
        return bool(client.direct_thread_add_users(int(thread_id), user_ids))
    except Exception:
        return False


def share_photo(client: Any, thread_id: str | int, path: Any) -> dict[str, Any]:
    """Send a photo into a conversation."""
    message = client.direct_send_photo(path, thread_ids=[int(thread_id)])
    return message_to_dict(message)
