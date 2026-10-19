"""Error types and instagrapi exception translation.

Every failure that reaches the CLI boundary is converted into a
:class:`SeraError` so the top-level handler can print a short, actionable
message instead of a Python traceback.
"""

from __future__ import annotations

from typing import Any


class SeraError(Exception):
    """Base class for all user-facing errors raised by the CLI."""

    exit_code = 1


class AuthError(SeraError):
    """Authentication failed or no usable session exists."""

    exit_code = 2


class NotFoundError(SeraError):
    """A thread, user, media or message could not be found."""

    exit_code = 3


class UsageError(SeraError):
    """The user asked for something that cannot work as requested."""

    exit_code = 4


class RateLimitError(SeraError):
    """Instagram asked us to slow down."""

    exit_code = 5


# (instagrapi exception name, the error we raise, the message we show).
# The names are looked up defensively: instagrapi renames its exceptions
# between releases, so a name that no longer exists is simply skipped and a
# missing class must never break the translator.
_HANDLERS: list[tuple[str, type[SeraError], str]] = [
    (
        "LoginRequired",
        AuthError,
        "Not logged in. Run `seraig auth login` or `seraig auth switch <username>`.",
    ),
    (
        "TwoFactorRequired",
        AuthError,
        "Two-factor authentication is required. Re-run `seraig auth login` and "
        "provide the 6-digit code from your authenticator app.",
    ),
    (
        "ChallengeRequired",
        AuthError,
        "Instagram requires a verification code. Re-run `seraig auth login` "
        "and enter the code sent by SMS or email.",
    ),
    (
        "ChallengeError",
        AuthError,
        "Instagram requires a verification code. Re-run `seraig auth login` "
        "and enter the code sent by SMS or email.",
    ),
    ("BadPassword", AuthError, "Incorrect password."),
    ("BadCredentials", AuthError, "Incorrect username or password."),
    (
        "AccountSuspended",
        AuthError,
        "Instagram has suspended this account.",
    ),
    (
        "FollowRequired",
        SeraError,
        "You need to follow this account before doing that.",
    ),
    (
        "RelatedProfileRequired",
        SeraError,
        "You need to follow this account before doing that.",
    ),
    ("NotFoundError", NotFoundError, "Instagram could not find the requested item."),
    ("DirectThreadNotFound", NotFoundError, "That conversation does not exist."),
    ("DirectMessageNotFound", NotFoundError, "That message does not exist."),
    ("UserNotFound", NotFoundError, "That Instagram user does not exist."),
    ("MediaNotFound", NotFoundError, "That media does not exist (or is private)."),
    ("MediaUnavailable", NotFoundError, "That media is not available."),
    ("CommentNotFound", NotFoundError, "That comment does not exist."),
    ("StoryNotFound", NotFoundError, "That story does not exist."),
    ("PleaseWaitFewMinutes", RateLimitError, "Too many requests — Instagram asked us to slow down."),
    ("RateLimitError", RateLimitError, "Too many requests — Instagram asked us to slow down."),
    ("TooManyRequests", RateLimitError, "Too many requests — Instagram asked us to slow down."),
    (
        "ClientThrottledError",
        RateLimitError,
        "Too many requests — Instagram asked us to slow down.",
    ),
    (
        "ProxyAddressIsBlocked",
        SeraError,
        "Instagram blocked this IP address. Try a different network.",
    ),
    ("SentryBlock", SeraError, "Instagram blocked this request. Try again in a few minutes."),
    ("WrongCursorError", SeraError, "Instagram rejected the request. Try again."),
    # The broad base classes come last: most instagrapi errors inherit from
    # PrivateError, so matching it early would swallow the specific ones.
    (
        "PrivateError",
        SeraError,
        "Instagram refused the request for a private account or restricted action.",
    ),
    ("PrivateAccount", SeraError, "That account is private."),
]


def translate(exc: Exception) -> SeraError:
    """Map an arbitrary exception onto a :class:`SeraError`.

    The instagrapi exception hierarchy is imported lazily so that importing
    :mod:`sera_ig.errors` stays cheap for the TUI and for tests. Exception
    names are resolved dynamically — instagrapi renames them between
    releases, and an unknown class must never crash the translator.
    """
    if isinstance(exc, SeraError):
        return exc

    try:
        from instagrapi import exceptions as ig_exc
    except Exception:  # pragma: no cover - instagrapi is a hard dependency
        return SeraError(str(exc))

    for name, error_class, message in _HANDLERS:
        instagrapi_class = getattr(ig_exc, name, None)
        if instagrapi_class is not None and isinstance(exc, instagrapi_class):
            return error_class(message)

    client_error = getattr(ig_exc, "ClientError", None)
    if client_error is not None and isinstance(exc, client_error):
        return SeraError(f"Instagram returned an error: {exc}")

    message = str(exc) or exc.__class__.__name__
    return SeraError(message)


def describe(exc: Exception) -> tuple[str, Any]:
    """Return a short human description for *exc* and its exit code."""
    translated = translate(exc)
    return str(translated), translated.exit_code
