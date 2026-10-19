"""Session and account management.

The CLI keeps one instagrapi session per Instagram account on disk. Sessions
are plain JSON (cookies, device identifiers and the authorization blob) so a
login only has to happen once per account; every later command restores the
session instead of hitting the login endpoint again.

Layout::

    <data_dir>/users/<username>/session.json
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from instagrapi import Client as InstagrapiClient
from instagrapi.exceptions import LoginRequired, TwoFactorRequired

from .config import Config, get_config
from .errors import AuthError, NotFoundError, SeraError

logger = logging.getLogger(__name__)

CodePrompt = Callable[[str, str], str | None]
"""``(username, channel) -> code`` — returns ``None`` to abort the challenge."""


class SeraClient(InstagrapiClient):
    """An instagrapi client with an interactive challenge-code handler.

    The base class ships a handler that reads from ``stdin`` directly. We
    replace it so the TUI and the JSON output mode stay in control of what is
    printed and when.
    """

    def __init__(self, *args: Any, code_prompt: CodePrompt | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._code_prompt: CodePrompt = code_prompt or self._default_code_prompt

    def _default_code_prompt(self, username: str, channel: str) -> str | None:
        """Ask the user for a verification code on the terminal."""
        prompts = {
            "totp": (
                f"Enter the 2FA code for @{username} "
                "(6 digits from your authenticator app, or the SMS/email code): "
            ),
            "sms": f"Enter the code sent to @{username} by SMS: ",
            "email": f"Enter the code sent to @{username} by email: ",
        }
        question = prompts.get(channel, f"Enter the verification code for @{username}: ")
        try:
            code = input(question).strip()
        except (EOFError, KeyboardInterrupt):
            return None
        return code or None

    def challenge_code_handler(self, username: str, choice: Any) -> str | None:  # type: ignore[override]
        """Handle an Instagram verification challenge (SMS / email code)."""
        channel = "sms" if str(choice).upper().endswith("SMS") else "email"
        return self._code_prompt(username, channel)

    def ask_two_factor_code(self, username: str) -> str | None:
        """Ask for the 2FA code when Instagram demands one mid-login."""
        return self._code_prompt(username, "totp")

    def totp_code(self, secret: str) -> str:
        """Generate the current 6-digit TOTP code for *secret*."""
        return self.totp_generate_code(secret.strip().replace(" ", "").upper())


class SessionManager:
    """Reads and writes per-account instagrapi sessions."""

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or get_config()

    # ------------------------------------------------------------- accounts
    def accounts(self) -> list[str]:
        """Return every account that has a session on disk."""
        users_dir = self.config.users_dir
        if not users_dir.exists():
            return []
        found = []
        for entry in users_dir.iterdir():
            if entry.is_dir() and (entry / "session.json").exists():
                found.append(entry.name)
        return sorted(found)

    def has_session(self, username: str) -> bool:
        return self.config.session_path(username).exists()

    def default_username(self) -> str | None:
        """Return the account the CLI should use when none is given."""
        current = self.config.get("login.current_username")
        if current and self.has_session(current):
            return current
        default = self.config.get("login.default_username")
        if default and self.has_session(default):
            return default
        accounts = self.accounts()
        return accounts[0] if accounts else None

    def resolve(self, account: str | None) -> str:
        """Return the account to use, or explain why we cannot."""
        if account:
            return account.lstrip("@").strip()
        username = self.default_username()
        if not username:
            raise AuthError(
                "No account is logged in. Run `seraig auth login` to add one, "
                "or pass `--account <username>`."
            )
        return username

    # -------------------------------------------------------------- storage
    def read_settings(self, username: str) -> dict[str, Any]:
        path = self.config.session_path(username)
        if not path.exists():
            raise AuthError(
                f"No session found for @{username}. Run `seraig auth login --account {username}`."
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise AuthError(
                f"The session file for @{username} is corrupted. "
                f"Run `seraig auth login --account {username}` to recreate it."
            ) from exc

    def write_settings(self, username: str, settings: dict[str, Any]) -> None:
        path = self.config.session_path(username)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass

    def delete_session(self, username: str) -> bool:
        path = self.config.session_path(username)
        if not path.exists():
            return False
        path.unlink()
        # Drop the (now empty) per-user directory when possible.
        try:
            path.parent.rmdir()
        except OSError:
            pass
        return True

    # -------------------------------------------------------------- clients
    def build_client(self, username: str | None = None) -> SeraClient:
        """Create a client with sane defaults, without touching the network."""
        timeout = self.config.get("advanced.request_timeout", 30) or 30
        client = SeraClient(
            request_timeout=timeout,
            delay_range=self.config.get("advanced.delay_range") or None,
        )
        if username:
            client.username = username
        return client

    def restore(self, username: str) -> SeraClient:
        """Load a stored session into a client (no network traffic)."""
        settings = self.read_settings(username)
        client = self.build_client(username)
        try:
            client.set_settings(settings)
        except Exception as exc:  # pragma: no cover - defensive
            raise AuthError(f"Could not restore the session for @{username}: {exc}") from exc
        client.username = username
        return client

    def save(self, client: SeraClient, username: str) -> None:
        """Persist the current client state (refreshed cookies included)."""
        self.write_settings(username, client.get_settings())


@contextmanager
def connect(
    account: str | None = None,
    *,
    manager: SessionManager | None = None,
    code_prompt: CodePrompt | None = None,
    validate: bool = False,
) -> Iterator[SeraClient]:
    """Yield a logged-in client for *account*.

    The stored session is restored and (optionally) validated with a cheap
    authenticated call. Session state is written back on exit so refreshed
    cookies survive the process.

    Validation is off by default: it costs a full network round trip before
    every command, and an expired session already surfaces as a
    ``LoginRequired`` from the command itself — which the CLI turns into a
    clear message. The interactive interfaces rely on this: they must draw
    their first frame immediately, not after a slow round trip.
    """
    manager = manager or SessionManager()
    username = manager.resolve(account)
    client = manager.restore(username)
    if code_prompt is not None:
        client._code_prompt = code_prompt

    if validate:
        try:
            client.account_info()
        except LoginRequired as exc:
            raise AuthError(
                f"The session for @{username} has expired. "
                f"Run `seraig auth login --account {username}` to sign in again."
            ) from exc

    try:
        yield client
    finally:
        try:
            manager.save(client, username)
        except Exception:  # pragma: no cover - never fail on save
            logger.debug("Could not persist the session for @%s", username, exc_info=True)


def resolve_totp_secret(explicit: str | None, config: Config | None = None) -> str | None:
    """Find the TOTP seed, in order: flag, environment, stored config.

    The seed is the base32 secret shown by Instagram when two-factor
    authentication is set up with an authenticator app. It is treated as a
    secret: it is never logged and never printed.
    """
    candidates = [explicit, os.environ.get("SERA_IG_TOTP_SECRET")]
    config = config or get_config()
    stored = config.get("login.totp_secret")
    if stored:
        candidates.append(str(stored))
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip().replace(" ", "").upper()
    return None


def login(
    username: str,
    password: str,
    *,
    verification_code: str = "",
    manager: SessionManager | None = None,
    code_prompt: CodePrompt | None = None,
    totp_secret: str | None = None,
) -> SeraClient:
    """Perform a fresh login and store the resulting session.

    Two-factor authentication is handled three ways, in order of preference:

    1. a TOTP seed is available — the current 6-digit code is generated
       locally, so the login needs no interaction at all;
    2. a code was passed in — it is used as-is (TOTP, SMS or a backup code);
    3. otherwise Instagram is asked for a code and the user is prompted.
    """
    manager = manager or SessionManager()
    client = manager.build_client(username)
    if code_prompt is not None:
        client._code_prompt = code_prompt

    if not verification_code:
        secret = resolve_totp_secret(totp_secret, manager.config)
        if secret:
            try:
                verification_code = client.totp_code(secret)
            except Exception as exc:
                logger.debug("Could not generate a TOTP code: %s", exc)

    try:
        client.login(username, password, verification_code=verification_code or "")
    except TwoFactorRequired:
        if verification_code:
            raise
        code = client.ask_two_factor_code(username)
        if not code:
            raise AuthError(
                "A verification code is required to finish signing in. "
                "Re-run `seraig auth login` and enter the code when asked, or "
                "store a TOTP seed with `seraig config set login.totp_secret <seed>`."
            ) from None
        client.login(username, password, verification_code=code)

    manager.write_settings(username, client.get_settings())
    manager.config.set("login.current_username", username)
    manager.config.set("login.default_username", username)
    return client


def _ask_two_factor_code(username: str, code_prompt: CodePrompt | None) -> str:
    """Ask the user for a 6-digit 2FA / verification code."""
    prompt = code_prompt or (lambda _u, _c: None)
    code = prompt(username, "totp")
    if not code:
        raise AuthError(
            "A verification code is required to finish signing in. "
            "Re-run `seraig auth login` and enter the code when asked, or "
            "store a TOTP seed with `seraig config set login.totp_secret <seed>`."
        )
    return code


def logout(
    username: str,
    *,
    manager: SessionManager | None = None,
    revoke: bool = True,
) -> bool:
    """Log out of Instagram and delete the local session."""
    manager = manager or SessionManager()
    if not manager.has_session(username):
        raise NotFoundError(f"No session found for @{username}.")

    if revoke:
        client = manager.restore(username)
        try:
            client.logout()
        except Exception as exc:  # pragma: no cover - network dependent
            logger.debug("Remote logout failed for @%s: %s", username, exc)

    manager.delete_session(username)
    config = manager.config
    if config.get("login.current_username") == username:
        config.set("login.current_username", None)
    if config.get("login.default_username") == username:
        config.set("login.default_username", None)
    return True


def session_path_for(username: str, config: Config | None = None) -> Path:
    """Return the on-disk path of a user's session file."""
    config = config or get_config()
    return config.session_path(username)


__all__ = [
    "SeraClient",
    "SessionManager",
    "SeraError",
    "connect",
    "login",
    "logout",
    "session_path_for",
]
