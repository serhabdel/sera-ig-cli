"""Session and account management tests."""

from __future__ import annotations

import json

import pytest

from sera_ig.client import SessionManager
from sera_ig.config import get_config
from sera_ig.errors import AuthError

from .fakes import FakeClient


def test_no_accounts_on_a_fresh_install(config) -> None:
    manager = SessionManager(config)
    assert manager.accounts() == []
    assert manager.default_username() is None


def test_missing_session_raises(config) -> None:
    manager = SessionManager(config)
    with pytest.raises(AuthError):
        manager.read_settings("nobody")


def test_settings_round_trip(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {"uuid": "abc"}, "cookies": {}})
    assert manager.has_session("noor") is True
    assert manager.read_settings("noor")["uuids"]["uuid"] == "abc"


def test_session_file_is_stored_with_restrictive_permissions(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}})
    mode = config.session_path("noor").stat().st_mode & 0o777
    assert mode == 0o600


def test_delete_session(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}})
    assert manager.delete_session("noor") is True
    assert manager.delete_session("noor") is False
    assert manager.accounts() == []


def test_default_username_prefers_the_current_account(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}})
    manager.write_settings("sara", {"uuids": {}})
    config.set("login.current_username", "sara")
    assert manager.default_username() == "sara"
    assert manager.accounts() == ["noor", "sara"]


def test_resolve_raises_without_an_account(config) -> None:
    manager = SessionManager(config)
    with pytest.raises(AuthError):
        manager.resolve(None)


def test_resolve_strips_the_at_sign(config) -> None:
    manager = SessionManager(config)
    assert manager.resolve("@noor") == "noor"


def test_restore_loads_the_stored_session(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {"uuid": "xyz"}, "cookies": {"a": "b"}})
    client = manager.restore("noor")
    assert client.username == "noor"
    assert client.get_settings()["uuids"]["uuid"] == "xyz"


def test_corrupted_session_is_reported(config) -> None:
    manager = SessionManager(config)
    path = config.session_path("noor")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(AuthError):
        manager.read_settings("noor")


def test_config_records_the_active_account(config) -> None:
    manager = SessionManager(config)
    manager.config.set("login.current_username", "noor")
    assert get_config().get("login.current_username") == "noor"


def test_fake_client_satisfies_the_session_interface() -> None:
    client = FakeClient()
    assert isinstance(json.dumps(client.get_settings()), str)


def test_request_delay_comes_from_the_config(config) -> None:
    """instagrapi's request_timeout is a pause between requests, not a timeout."""
    manager = SessionManager(config)
    config.set("advanced.request_delay", 1)
    assert manager.build_client().request_timeout == 1

    config.set("advanced.request_delay", 0)
    assert manager.build_client().request_timeout == 0


def test_a_stored_session_cannot_override_the_request_delay(config) -> None:
    """A session saved by an older version must not restore a stale delay."""
    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}, "request_timeout": 30})
    config.set("advanced.request_delay", 1)

    client = manager.restore("noor")
    assert client.request_timeout == 1


def test_connect_does_not_block_on_a_network_call(monkeypatch, config) -> None:
    """Restoring a session must not make a request.

    The interactive interfaces draw their first frame straight away, so the
    up-front validation round trip would leave them blank on a slow link.
    """
    from sera_ig import client as client_module

    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}, "cookies": {}})

    calls: list[str] = []

    class SlowClient:
        username = "noor"
        user_id = 1

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def set_settings(self, settings: dict) -> bool:
            return True

        def account_info(self):
            calls.append("account_info")
            raise AssertionError("connect() must not validate up front")

    monkeypatch.setattr(manager, "build_client", lambda username=None: SlowClient())
    monkeypatch.setattr(client_module, "SessionManager", lambda config=None: manager)

    with client_module.connect("noor", manager=manager) as client:
        assert client.username == "noor"
    assert calls == []


def test_connect_can_still_validate(monkeypatch, config) -> None:
    """The validation is opt-in, and it reports an expired session clearly."""
    from instagrapi.exceptions import LoginRequired

    from sera_ig import client as client_module

    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}, "cookies": {}})

    class DeadClient:
        username = "noor"
        user_id = 1

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def set_settings(self, settings: dict) -> bool:
            return True

        def account_info(self):
            raise LoginRequired("expired")

    monkeypatch.setattr(manager, "build_client", lambda username=None: DeadClient())

    with pytest.raises(AuthError) as excinfo:
        with client_module.connect("noor", manager=manager, validate=True):
            pass
    assert "expired" in str(excinfo.value)


def test_a_logged_out_session_names_the_account(monkeypatch, config) -> None:
    """When Instagram logs the session out, say which account and what to do."""
    from instagrapi.exceptions import LoginRequired

    from sera_ig import client as client_module

    manager = SessionManager(config)
    manager.write_settings("noor", {"uuids": {}, "cookies": {}})

    class LoggedOutClient:
        username = "noor"
        user_id = 1

        def get_settings(self) -> dict:
            return {"uuids": {}}

        def set_settings(self, settings: dict) -> bool:
            return True

    monkeypatch.setattr(manager, "build_client", lambda username=None: LoggedOutClient())

    with pytest.raises(AuthError) as excinfo:
        with client_module.connect("noor", manager=manager):
            raise LoginRequired("logged out")
    message = str(excinfo.value)
    assert "@noor" in message
    assert "seraig auth login" in message
