"""Two-factor authentication tests.

The 2FA round trip is the part of the login flow most likely to break, and
the most likely to break for a real user, so it gets its own file.
"""

from __future__ import annotations

import pytest

from sera_ig.client import (
    SessionManager,
    login,
    resolve_totp_secret,
)
from sera_ig.errors import AuthError

# A well-known RFC 6238 test vector: secret "GEZDGNBVGY3TQOJQ" always
# produces 254676 for the standard 30 second window.
TEST_SEED = "GEZDGNBVGY3TQOJQ"


def test_totp_code_is_generated_from_the_seed() -> None:
    from sera_ig.client import SeraClient

    client = SeraClient()
    code = client.totp_code(TEST_SEED)
    assert code.isdigit()
    assert len(code) == 6


def test_totp_seed_is_normalised() -> None:
    assert resolve_totp_secret("gezd gnbv gy3t qojq") == TEST_SEED
    assert resolve_totp_secret(" GEZDGNBVGY3TQOJQ ") == TEST_SEED


def test_totp_seed_prefers_the_flag(monkeypatch, config) -> None:
    monkeypatch.setenv("SERA_IG_TOTP_SECRET", "ENVVSEED")
    assert resolve_totp_secret("FLAGSEED", config) == "FLAGSEED"


def test_totp_seed_falls_back_to_the_environment(monkeypatch, config) -> None:
    monkeypatch.setenv("SERA_IG_TOTP_SECRET", "ENVVSEED")
    assert resolve_totp_secret(None, config) == "ENVVSEED"


def test_totp_seed_falls_back_to_the_config(monkeypatch, config) -> None:
    monkeypatch.delenv("SERA_IG_TOTP_SECRET", raising=False)
    config.set("login.totp_secret", TEST_SEED)
    assert resolve_totp_secret(None, config) == TEST_SEED


def test_no_totp_seed_anywhere(monkeypatch, config) -> None:
    monkeypatch.delenv("SERA_IG_TOTP_SECRET", raising=False)
    assert resolve_totp_secret(None, config) is None


def test_login_uses_a_generated_totp_code(monkeypatch, config) -> None:
    """A stored seed means the login needs no interaction at all."""
    calls: list[dict] = []

    class FakeClient:
        username = "noor"
        user_id = 42

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def login(self, username, password, verification_code="", **kwargs):
            calls.append({"password": password, "code": verification_code})
            return True

        def totp_generate_code(self, seed: str) -> str:
            calls.append({"seed": seed})
            return "123456"

        def totp_code(self, secret: str) -> str:
            return self.totp_generate_code(secret)

    manager = SessionManager(config)
    manager.build_client = lambda username=None: FakeClient()  # type: ignore[method-assign]
    config.set("login.totp_secret", TEST_SEED)

    login("noor", "pw", manager=manager)

    assert calls[0]["seed"] == TEST_SEED
    assert calls[1]["code"] == "123456"


def test_login_asks_for_the_code_when_two_factor_is_required(monkeypatch, config) -> None:
    """Without a seed, the user is prompted for the 2FA code."""
    attempts: list[str] = []

    class FakeClient:
        username = "noor"
        user_id = 42

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def login(self, username, password, verification_code="", **kwargs):
            attempts.append(verification_code)
            if not verification_code:
                from instagrapi.exceptions import TwoFactorRequired

                raise TwoFactorRequired("two factor required")
            return True

        def ask_two_factor_code(self, username: str) -> str:
            return "654321"

    manager = SessionManager(config)
    manager.build_client = lambda username=None: FakeClient()  # type: ignore[method-assign]

    login("noor", "pw", manager=manager)

    assert attempts == ["", "654321"]


def test_login_reports_a_missing_code(monkeypatch, config) -> None:
    class FakeClient:
        username = "noor"
        user_id = 42

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def login(self, username, password, verification_code="", **kwargs):
            from instagrapi.exceptions import TwoFactorRequired

            raise TwoFactorRequired("two factor required")

        def ask_two_factor_code(self, username: str) -> str:
            return ""

    manager = SessionManager(config)
    manager.build_client = lambda username=None: FakeClient()  # type: ignore[method-assign]

    with pytest.raises(AuthError) as excinfo:
        login("noor", "pw", manager=manager)
    assert "verification code" in str(excinfo.value).lower()


def test_login_with_an_explicit_code_skips_the_prompt(monkeypatch, config) -> None:
    attempts: list[str] = []

    class FakeClient:
        username = "noor"
        user_id = 42

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def login(self, username, password, verification_code="", **kwargs):
            attempts.append(verification_code)
            return True

        def ask_two_factor_code(self, username: str) -> str:
            raise AssertionError("should not prompt when a code was supplied")

    manager = SessionManager(config)
    manager.build_client = lambda username=None: FakeClient()  # type: ignore[method-assign]

    login("noor", "pw", verification_code="112233", manager=manager)

    assert attempts == ["112233"]


def test_default_prompt_mentions_the_authenticator_app(monkeypatch) -> None:
    from sera_ig.client import SeraClient

    asked: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt="": asked.append(prompt) or "123456")
    client = SeraClient()
    assert client.ask_two_factor_code("noor") == "123456"
    assert "authenticator app" in asked[0]
