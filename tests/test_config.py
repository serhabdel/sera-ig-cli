"""Configuration store tests."""

from __future__ import annotations

from sera_ig.config import Config, get_config, reset_config_cache


def test_defaults_are_created(config: Config) -> None:
    assert config.path.exists()
    assert config.get("chat.page_size") == 20
    assert config.get("login.current_username") is None


def test_dot_notation_get_and_set(config: Config) -> None:
    config.set("chat.page_size", 99)
    assert config.get("chat.page_size") == 99
    config.set("chat.new_key", "value")
    assert config.get("chat.new_key") == "value"


def test_unknown_key_returns_default(config: Config) -> None:
    assert config.get("does.not.exist") is None
    assert config.get("does.not.exist", "fallback") == "fallback"


def test_values_persist_across_instances(config: Config) -> None:
    config.set("advanced.debug", True)
    reset_config_cache()
    assert get_config().get("advanced.debug") is True


def test_unset_removes_key(config: Config) -> None:
    config.set("chat.page_size", 5)
    assert config.unset("chat.page_size") is True
    assert config.get("chat.page_size") == 20  # falls back to the default
    assert config.unset("chat.page_size") is False


def test_items_are_flattened(config: Config) -> None:
    keys = [key for key, _ in config.items()]
    assert "chat.page_size" in keys
    assert "login.current_username" in keys


def test_reset_restores_defaults(config: Config) -> None:
    config.set("chat.page_size", 1234)
    config.reset()
    assert config.get("chat.page_size") == 20
