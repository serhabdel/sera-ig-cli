"""Resolving a human reference to an Instagram DM thread.

``seraig read <thread>`` accepts any of:

* a numeric thread id — ``340282366841510300949128268610842297468``
* a username — ``@noor`` or ``noor``
* a fuzzy thread title — ``weekend plans``

Resolution order is: exact thread id, then exact username, then fuzzy match on
usernames and titles. When nothing matches and exactly one candidate account
was meant, a fresh thread is opened for that user.
"""

from __future__ import annotations

import difflib
from typing import Any

from instagrapi.types import DirectThread

from .errors import NotFoundError, UsageError

THREAD_ID_MIN_LEN = 6


def thread_usernames(thread: DirectThread) -> list[str]:
    """All usernames taking part in *thread*."""
    return [u.username for u in thread.users if u.username]


def thread_title(thread: DirectThread) -> str:
    """Best available human label for *thread*."""
    if thread.thread_title:
        return thread.thread_title
    usernames = thread_usernames(thread)
    if not usernames:
        return f"thread {thread.id}"
    if len(usernames) == 1:
        return usernames[0]
    return ", ".join(usernames[:3]) + ("…" if len(usernames) > 3 else "")


def _norm(value: str) -> str:
    return (value or "").strip().lstrip("@").lower()


def looks_like_thread_id(reference: str) -> bool:
    """True when *reference* is plausibly a raw thread id."""
    candidate = (reference or "").strip()
    return candidate.isdigit() and len(candidate) >= THREAD_ID_MIN_LEN


def resolve_thread(
    client: Any,
    reference: str,
    *,
    threads: list[DirectThread] | None = None,
    create: bool = False,
) -> DirectThread:
    """Resolve *reference* to a :class:`DirectThread`.

    Raises :class:`NotFoundError` when nothing matches and *create* is false.

    The number of requests matters here: a thread id is fetched directly with
    one request, and a name is looked up by paging through the inbox and
    stopping at the first page that matches.
    """
    reference = (reference or "").strip()
    if not reference:
        raise UsageError("No thread reference given.")

    # 1. A thread id: fetch exactly that thread, in one request.
    if looks_like_thread_id(reference):
        try:
            return client.direct_thread(int(reference), amount=1)
        except Exception as exc:
            raise NotFoundError(f"No thread with id {reference}.") from exc

    # 2. A name: page through the inbox until it matches.
    if threads is None:
        found, seen = _search_inbox(client, reference)
    else:
        found = _match(threads, reference)
        seen = threads

    if found is not None:
        return found

    # 3. A new thread for an existing user.
    if create:
        return _create_thread(client, _norm(reference))

    suggestions = _suggest(reference, seen)
    hint = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    raise NotFoundError(
        f"No thread matching '{reference}'.{hint} "
        "Pass a thread id, a username, or use `seraig search <name>` to find a user."
    )


def _match(threads: list[DirectThread], reference: str) -> DirectThread | None:
    """Find the thread matching *reference* in a list of threads."""
    wanted = _norm(reference)

    # An exact username wins.
    exact = [
        thread
        for thread in threads
        if any(_norm(username) == wanted for username in thread_usernames(thread))
    ]
    if exact:
        # Prefer the most recently active thread for that user.
        exact.sort(key=lambda thread: thread.last_activity_at or 0, reverse=True)
        return exact[0]

    # Then a fuzzy match on the usernames and the titles.
    return _fuzzy_match(reference, threads)


def _search_inbox(client: Any, reference: str) -> tuple[DirectThread | None, list[DirectThread]]:
    """Page through the inbox until *reference* matches.

    Only one page is fetched when the conversation is in the first page, which
    is the usual case. An exact username match keeps priority over a fuzzy
    one, so the pages are scanned until it is found or the inbox runs out.
    """
    seen: list[DirectThread] = []
    fuzzy: DirectThread | None = None
    cursor: str | None = None

    while True:
        try:
            chunk, cursor = client.direct_threads_chunk(None, None, 1, cursor)
        except Exception:
            break
        if not chunk:
            break
        seen.extend(chunk)

        exact = _exact_username(reference, chunk)
        if exact is not None:
            return exact, seen
        if fuzzy is None:
            fuzzy = _fuzzy_match(reference, chunk)
        if not cursor:
            break

    return fuzzy, seen


def _exact_username(reference: str, threads: list[DirectThread]) -> DirectThread | None:
    """Return the thread of the user named exactly *reference*."""
    wanted = _norm(reference)
    exact = [
        thread
        for thread in threads
        if any(_norm(username) == wanted for username in thread_usernames(thread))
    ]
    if not exact:
        return None
    exact.sort(key=lambda thread: thread.last_activity_at or 0, reverse=True)
    return exact[0]


def _fuzzy_match(reference: str, threads: list[DirectThread]) -> DirectThread | None:
    """Fuzzy match on usernames first, then on thread titles."""
    wanted = _norm(reference)
    if not wanted:
        return None

    for thread in threads:
        for username in thread_usernames(thread):
            if _norm(username) == wanted:
                return thread

    # Substring match on a username.
    partial = [
        thread
        for thread in threads
        if any(wanted in _norm(username) for username in thread_usernames(thread))
    ]
    if len(partial) == 1:
        return partial[0]

    # Substring match on the thread title.
    titled = [thread for thread in threads if wanted in (thread.thread_title or "").lower()]
    if len(titled) == 1:
        return titled[0]

    # Fuzzy (edit distance) match over usernames and titles.
    candidates: list[tuple[float, DirectThread]] = []
    for thread in threads:
        labels = thread_usernames(thread) + [thread.thread_title or ""]
        for label in labels:
            score = difflib.SequenceMatcher(None, wanted, _norm(label)).ratio()
            if score >= 0.72:
                candidates.append((score, thread))
    if candidates:
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return candidates[0][1]
    return None


def _create_thread(client: Any, username: str) -> DirectThread:
    """Open a brand new thread with *username*."""
    try:
        user = client.user_info_by_username(username)
    except Exception as exc:
        raise NotFoundError(f"Could not find an Instagram account named '{username}'.") from exc

    try:
        payload = client.direct_thread_by_participants([int(user.pk)])
    except Exception as exc:
        raise NotFoundError(
            f"Could not open a thread with @{username}. "
            "Make sure you can message this account."
        ) from exc

    thread_id = payload.get("thread_id") if isinstance(payload, dict) else None
    if thread_id is None:
        raise NotFoundError(f"Could not open a thread with @{username}.")
    return client.direct_thread(int(thread_id), amount=1)


def _suggest(reference: str, threads: list[DirectThread], limit: int = 5) -> list[str]:
    """Return up to *limit* thread labels close to *reference*."""
    wanted = _norm(reference)
    labels: list[str] = []
    for thread in threads:
        label = thread_title(thread)
        if label and label not in labels:
            labels.append(label)
    matches = difflib.get_close_matches(
        wanted, [label.lower() for label in labels], n=limit, cutoff=0.4
    )
    if matches:
        lowered = {label.lower(): label for label in labels}
        return [lowered[match] for match in matches]
    return labels[:limit]
