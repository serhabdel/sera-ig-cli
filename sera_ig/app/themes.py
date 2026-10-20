"""The theme registry.

Textual ships a large set of built-in themes. On top of those, a user can
drop JSON files into ``~/.sera-ig-cli/themes/`` to define their own::

    {
      "primary": "#88C0D0",
      "secondary": "#81A1C1",
      "accent": "#B48EAD",
      "background": "#2E3440",
      "variables": { "panel": "#3B4252" }
    }

The file name (without the extension) is the theme name.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..config import Config, get_config

logger = logging.getLogger(__name__)

DEFAULT_THEME = "textual-dark"
THEMES_DIRNAME = "themes"


def builtin_themes() -> dict[str, Any]:
    """Return the themes Textual provides out of the box."""
    from textual.theme import BUILTIN_THEMES

    return dict(BUILTIN_THEMES)


def themes_dir(config: Config | None = None) -> Path:
    """Return the directory holding user theme files."""
    config = config or get_config()
    return config.data_dir / THEMES_DIRNAME


def load_user_theme(path: Path) -> Any | None:
    """Load a theme from a JSON file, or return ``None`` if it is unusable."""
    from textual.theme import Theme

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Ignoring theme %s: %s", path.name, exc)
        return None

    if not isinstance(raw, dict):
        logger.warning("Ignoring theme %s: not a JSON object", path.name)
        return None

    name = str(raw.pop("name", path.stem))
    variables = raw.pop("variables", None)
    if isinstance(variables, dict):
        raw["variables"] = {str(k): str(v) for k, v in variables.items()}
    else:
        raw.pop("variables", None)

    for key in ("primary", "secondary"):
        if key not in raw:
            logger.warning("Ignoring theme %s: missing %r", path.name, key)
            return None

    try:
        return Theme(name=name, **raw)
    except TypeError as exc:
        logger.warning("Ignoring theme %s: %s", path.name, exc)
        return None


def user_themes(config: Config | None = None) -> dict[str, Any]:
    """Load every user theme file, skipping the ones that do not parse."""
    directory = themes_dir(config)
    found: dict[str, Any] = {}
    if not directory.exists():
        return found
    for path in sorted(directory.glob("*.json")):
        theme = load_user_theme(path)
        if theme is not None:
            found[theme.name] = theme
    return found


def available_themes(config: Config | None = None) -> list[str]:
    """Return the names of every usable theme, built-in first."""
    return sorted(set(builtin_themes()) | set(user_themes(config)))


def resolve_theme(name: str, config: Config | None = None) -> Any | None:
    """Return the theme called *name*, or ``None`` when there is no such theme."""
    if not name:
        return None
    return user_themes(config).get(name) or builtin_themes().get(name)


def theme_summary(name: str, config: Config | None = None) -> dict[str, Any] | None:
    """Return a plain dict describing a theme, for the CLI and the tests."""
    theme = resolve_theme(name, config)
    if theme is None:
        return None
    return {
        "name": theme.name,
        "primary": theme.primary,
        "secondary": theme.secondary,
        "accent": theme.accent,
        "background": theme.background,
        "foreground": theme.foreground,
        "surface": theme.surface,
        "panel": theme.panel,
        "dark": theme.dark,
        "variables": dict(theme.variables),
    }
