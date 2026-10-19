"""Configuration and on-disk layout.

Everything the CLI persists lives under a single root directory (by default
``~/.sera-ig-cli``)::

    ~/.sera-ig-cli/
    ├── config.yaml            # user configuration
    ├── users/<username>/
    │   └── session.json       # instagrapi session (cookies + device)
    ├── logs/                  # rolling debug logs
    └── downloads/             # default download target

The root can be overridden with the ``SERA_IG_HOME`` environment variable,
which keeps tests and CI hermetic.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "login": {
        "default_username": None,
        "current_username": None,
        "totp_secret": None,
    },
    "chat": {
        "read_receipts": True,
        "mark_seen_on_open": True,
        "page_size": 20,
    },
    "output": {
        "format": "text",  # "text" or "json"
        "timestamps": True,
    },
    "ui": {
        "banner": True,
        "color": True,
    },
    "advanced": {
        "data_dir": None,  # filled in below
        "request_timeout": 30,
        "debug": False,
    },
}


def data_dir() -> Path:
    """Return the root directory used for all persisted state."""
    override = os.environ.get("SERA_IG_HOME")
    if override:
        return Path(override).expanduser().resolve()
    return Path.home() / ".sera-ig-cli"


def _default_config() -> dict[str, Any]:
    cfg = _deep_copy(DEFAULT_CONFIG)
    cfg["advanced"]["data_dir"] = str(data_dir())
    return cfg


def _deep_copy(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _deep_copy(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_deep_copy(v) for v in value]
    return value


class Config:
    """Small YAML-backed config store with dot-notation access.

    The class is intentionally forgiving: unknown keys read back as ``None``
    and unknown writes create the intermediate dictionaries.
    """

    def __init__(self, path: Path | None = None) -> None:
        self.data_dir = data_dir()
        self.path = path or (self.data_dir / "config.yaml")
        self._data: dict[str, Any] = {}
        self.load()

    # ------------------------------------------------------------------ load
    def load(self) -> None:
        """Read the config file, falling back to defaults."""
        defaults = _default_config()
        if not self.path.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._data = defaults
            self.save()
            return
        try:
            raw = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        self._data = _merge(defaults, raw)

    def save(self) -> None:
        """Write the config back to disk.

        The file may hold the two-factor seed, so it is kept private.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(self._data, fh, default_flow_style=False, sort_keys=False)
        try:
            self.path.chmod(0o600)
        except OSError:  # pragma: no cover - platform dependent
            pass

    # ------------------------------------------------------------- accessors
    def get(self, key: str, default: Any = None) -> Any:
        """Read ``key`` using dot notation, e.g. ``chat.page_size``.

        Falls back to the factory default when the key was removed from the
        file, and to *default* when neither the file nor the defaults know it.
        """
        for source in (self._data, _default_config()):
            node: Any = source
            for part in key.split("."):
                if not isinstance(node, dict) or part not in node:
                    node = None
                    break
                node = node[part]
            if node is not None:
                return node
        return default

    def set(self, key: str, value: Any) -> None:
        """Write ``key`` using dot notation, creating parents as needed."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        node[parts[-1]] = value
        self.save()

    def unset(self, key: str) -> bool:
        """Remove ``key``. Returns ``True`` when something was removed."""
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        if isinstance(node, dict) and parts[-1] in node:
            del node[parts[-1]]
            self.save()
            return True
        return False

    def items(self) -> list[tuple[str, Any]]:
        """Return a flat ``(dotted.key, value)`` list of every setting."""
        flat: list[tuple[str, Any]] = []

        def walk(node: Any, prefix: str = "") -> None:
            if isinstance(node, dict):
                for key, value in node.items():
                    walk(value, f"{prefix}.{key}" if prefix else str(key))
            else:
                flat.append((prefix, node))

        walk(self._data)
        return flat

    def reset(self) -> None:
        """Restore the factory defaults."""
        self._data = _default_config()
        self.save()

    # ------------------------------------------------------------- path help
    @property
    def users_dir(self) -> Path:
        return self.data_dir / "users"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def downloads_dir(self) -> Path:
        return self.data_dir / "downloads"

    def user_dir(self, username: str) -> Path:
        return self.users_dir / username

    def session_path(self, username: str) -> Path:
        return self.user_dir(username) / "session.json"

    def ensure_dirs(self) -> None:
        for path in (self.data_dir, self.users_dir, self.logs_dir, self.downloads_dir):
            path.mkdir(parents=True, exist_ok=True)


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into a copy of *base*."""
    result = _deep_copy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


_config: Config | None = None


def get_config() -> Config:
    """Return the process-wide config singleton."""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reset_config_cache() -> None:
    """Drop the cached config — used by tests that move ``SERA_IG_HOME``."""
    global _config
    _config = None
