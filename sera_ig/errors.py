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


def translate(exc: Exception) -> SeraError:
    """Map an arbitrary exception onto a :class:`SeraError`.

    The instagrapi exception hierarchy is imported lazily so that importing
    :mod:`sera_ig.errors` stays cheap for the TUI and for tests.
    """
    try:
        from instagrapi import exceptions as ig_exc
    except Exception:  # pragma: no cover - instagrapi is a hard dependency
        return SeraError(str(exc))

    if isinstance(exc, SeraError):
        return exc
    if isinstance(exc, ig_exc.LoginRequired):
        return AuthError(
            "Not logged in. Run `seraig auth login` or `seraig auth switch <username>`."
        )
    if isinstance(exc, ig_exc.TwoFactorRequired):
        return AuthError(
            "Two-factor authentication is required. Re-run `seraig auth login` and "
            "provide the 6-digit code from your authenticator app."
        )
    if isinstance(exc, ig_exc.ChallengeRequired):
        return AuthError(
            "Instagram requires a verification code. Re-run `seraig auth login` "
            "and enter the code sent by SMS or email."
        )
    if isinstance(exc, ig_exc.PrivateError):
        return SeraError(
            "Instagram refused the request for a private account or restricted action."
        )
    if isinstance(exc, ig_exc.FollowRequired):
        return SeraError("You need to follow this account before doing that.")
    if isinstance(exc, ig_exc.NotFoundError):
        return NotFoundError("Instagram could not find the requested item.")
    if isinstance(exc, ig_exc.BadPassword):
        return AuthError("Incorrect password.")
    if isinstance(exc, ig_exc.UserNotFound):
        return NotFoundError("That Instagram user does not exist.")
    if isinstance(exc, ig_exc.MediaNotFound):
        return NotFoundError("That media does not exist (or is private).")
    if isinstance(exc, ig_exc.ClientError):
        return SeraError(f"Instagram returned an error: {exc}")
    if isinstance(exc, ig_exc.TooManyRequests):
        return RateLimitError("Too many requests — Instagram asked us to slow down.")

    message = str(exc) or exc.__class__.__name__
    return SeraError(message)


def describe(exc: Exception) -> tuple[str, Any]:
    """Return a short human description for *exc* and its raw message."""
    translated = translate(exc)
    return translated.message, translated.exit_code
