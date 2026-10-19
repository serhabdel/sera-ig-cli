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
    manager.write_settings("abdel", {"uuids": {"uuid": "abc"}, "cookies": {}})
    assert manager.has_session("abdel") is True
    assert manager.read_settings("abdel")["uuids"]["uuid"] == "abc"


def test_session_file_is_stored_with_restrictive_permissions(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("abdel", {"uuids": {}})
    mode = config.session_path("abdel").stat().st_mode & 0o777
    assert mode == 0o600


def test_delete_session(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("abdel", {"uuids": {}})
    assert manager.delete_session("abdel") is True
    assert manager.delete_session("abdel") is False
    assert manager.accounts() == []


def test_default_username_prefers_the_current_account(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("abdel", {"uuids": {}})
    manager.write_settings("sara", {"uuids": {}})
    config.set("login.current_username", "sara")
    assert manager.default_username() == "sara"
    assert manager.accounts() == ["abdel", "sara"]


def test_resolve_raises_without_an_account(config) -> None:
    manager = SessionManager(config)
    with pytest.raises(AuthError):
        manager.resolve(None)


def test_resolve_strips_the_at_sign(config) -> None:
    manager = SessionManager(config)
    assert manager.resolve("@abdel") == "abdel"


def test_restore_loads_the_stored_session(config) -> None:
    manager = SessionManager(config)
    manager.write_settings("abdel", {"uuids": {"uuid": "xyz"}, "cookies": {"a": "b"}})
    client = manager.restore("abdel")
    assert client.username == "abdel"
    assert client.get_settings()["uuids"]["uuid"] == "xyz"


def test_corrupted_session_is_reported(config) -> None:
    manager = SessionManager(config)
    path = config.session_path("abdel")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(AuthError):
        manager.read_settings("abdel")


def test_config_records_the_active_account(config) -> None:
    manager = SessionManager(config)
    manager.config.set("login.current_username", "abdel")
    assert get_config().get("login.current_username") == "abdel"


def test_fake_client_satisfies_the_session_interface() -> None:
    client = FakeClient()
    assert isinstance(json.dumps(client.get_settings()), str)
