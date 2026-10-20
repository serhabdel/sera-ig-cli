"""Tests for the theme registry."""

from __future__ import annotations

import json

from sera_ig.app.themes import (
    DEFAULT_THEME,
    available_themes,
    builtin_themes,
    load_user_theme,
    resolve_theme,
    theme_summary,
    themes_dir,
    user_themes,
)

VALID = {
    "primary": "#88C0D0",
    "secondary": "#81A1C1",
    "accent": "#B48EAD",
    "background": "#2E3440",
    "variables": {"panel": "#3B4252"},
}


def write_theme(config, name: str, payload: dict) -> None:
    directory = themes_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_builtin_themes_are_available() -> None:
    builtins = builtin_themes()
    assert "textual-dark" in builtins
    assert "nord" in builtins
    assert len(builtins) >= 7


def test_default_theme_exists() -> None:
    assert resolve_theme(DEFAULT_THEME) is not None


def test_available_themes_includes_the_builtins(config) -> None:
    names = available_themes(config)
    assert "textual-dark" in names
    assert "nord" in names


def test_a_user_theme_file_is_loaded(config) -> None:
    write_theme(config, "arctic", VALID)
    themes = user_themes(config)
    assert "arctic" in themes
    assert themes["arctic"].primary == "#88C0D0"
    assert themes["arctic"].variables["panel"] == "#3B4252"


def test_a_user_theme_shadows_a_builtin(config) -> None:
    payload = dict(VALID, primary="#FF0000")
    write_theme(config, "nord", payload)
    theme = resolve_theme("nord", config)
    assert theme.primary == "#FF0000"


def test_a_malformed_theme_file_is_skipped(config) -> None:
    directory = themes_dir(config)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "broken.json").write_text("{not json", encoding="utf-8")
    assert user_themes(config) == {}


def test_a_theme_without_the_required_colours_is_skipped(config) -> None:
    write_theme(config, "half", {"primary": "#FFFFFF"})
    assert user_themes(config) == {}


def test_a_theme_that_is_not_an_object_is_skipped(config) -> None:
    write_theme(config, "listy", [1, 2, 3])
    assert user_themes(config) == {}


def test_load_user_theme_returns_none_for_a_missing_file(config) -> None:
    assert load_user_theme(themes_dir(config) / "nope.json") is None


def test_theme_summary_describes_a_theme(config) -> None:
    summary = theme_summary("nord", config)
    assert summary is not None
    assert summary["name"] == "nord"
    assert summary["primary"].startswith("#")


def test_theme_summary_is_none_for_an_unknown_theme(config) -> None:
    assert theme_summary("does-not-exist", config) is None


def test_the_theme_round_trips_through_the_config(config) -> None:
    config.set("ui.theme", "nord")
    assert config.get("ui.theme") == "nord"
    assert theme_summary(config.get("ui.theme"), config)["name"] == "nord"
