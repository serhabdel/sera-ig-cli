"""Tests for the error translation layer.

The translator is the last line of defence: a bug in it turns a friendly
message into a traceback, so it has to survive anything instagrapi throws.
"""

from __future__ import annotations

import pytest

from sera_ig.errors import (
    AuthError,
    NotFoundError,
    RateLimitError,
    SeraError,
    UsageError,
    describe,
    translate,
)


def test_sera_errors_pass_through() -> None:
    error = UsageError("do it differently")
    assert translate(error) is error


def test_unknown_exceptions_become_sera_errors() -> None:
    translated = translate(RuntimeError("something odd"))
    assert isinstance(translated, SeraError)
    assert "something odd" in str(translated)


def test_missing_exception_names_do_not_break_the_translator() -> None:
    """instagrapi renames exceptions; an unknown name must not raise."""
    from instagrapi import exceptions as ig_exc

    for name in ig_exc.__all__ if hasattr(ig_exc, "__all__") else dir(ig_exc):
        if not name[0].isupper():
            continue
        error_class = getattr(ig_exc, name, None)
        if not isinstance(error_class, type) or not issubclass(error_class, Exception):
            continue
        # Translating must never raise, whatever the exception is.
        assert isinstance(translate(error_class("boom")), SeraError)


def test_login_required_is_an_auth_error() -> None:
    from instagrapi.exceptions import LoginRequired

    assert isinstance(translate(LoginRequired("nope")), AuthError)


def test_two_factor_is_an_auth_error() -> None:
    from instagrapi.exceptions import TwoFactorRequired

    assert isinstance(translate(TwoFactorRequired("nope")), AuthError)


def test_user_not_found_is_a_not_found_error() -> None:
    from instagrapi.exceptions import UserNotFound

    assert isinstance(translate(UserNotFound("nope")), NotFoundError)


def test_rate_limit_is_recognised() -> None:
    from instagrapi.exceptions import PleaseWaitFewMinutes

    assert isinstance(translate(PleaseWaitFewMinutes("slow down")), RateLimitError)


def test_describe_returns_the_message_and_code() -> None:
    message, code = describe(UsageError("nope"))
    assert message == "nope"
    assert code == UsageError.exit_code


def test_exit_codes_are_distinct() -> None:
    codes = {
        SeraError.exit_code,
        AuthError.exit_code,
        NotFoundError.exit_code,
        UsageError.exit_code,
        RateLimitError.exit_code,
    }
    assert len(codes) == 5


@pytest.mark.parametrize("name", ["LoginRequired", "TooManyRequests", "PrivateError", "FollowRequired"])
def test_handler_names_are_resolved_safely(name: str) -> None:
    """A name that no longer exists in instagrapi must be skipped, not fatal."""
    from instagrapi import exceptions as ig_exc

    from sera_ig.errors import _HANDLERS

    known = {entry[0] for entry in _HANDLERS}
    assert name in known

    if hasattr(ig_exc, name):
        error_class = getattr(ig_exc, name)
        translated = translate(error_class("boom"))
        assert isinstance(translated, SeraError)
    else:
        # The class is gone in this version; the translator must simply not
        # match it — and must not raise while looking it up.
        assert isinstance(translate(ValueError("boom")), SeraError)
