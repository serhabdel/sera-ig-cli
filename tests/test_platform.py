"""Platform compatibility tests.

The TUI is the only part of the CLI that is not pure Python: it needs
``curses``, which Windows does not ship. These tests make sure the
degradation is graceful instead of an ImportError traceback.
"""

from __future__ import annotations

import importlib
import sys

import pytest

from sera_ig.errors import SeraError
from sera_ig.tui import curses_available


def test_tui_module_imports_cleanly() -> None:
    """Importing the TUI package must never explode."""
    module = importlib.import_module("sera_ig.tui")
    assert hasattr(module, "run_chat")
    assert hasattr(module, "run_feed")


def test_curses_availability_matches_the_platform() -> None:
    if sys.platform == "win32":
        # windows-curses provides the module; either way the flag is correct.
        assert isinstance(curses_available(), bool)
    else:
        assert curses_available() is True


def test_missing_curses_gives_a_friendly_error(monkeypatch) -> None:
    """Simulate a platform without curses and check the message."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "curses" or name.startswith("curses."):
            raise ImportError("No module named 'curses'")
        return real_import(name, *args, **kwargs)

    for name in [n for n in sys.modules if n.startswith("sera_ig.tui")]:
        del sys.modules[name]

    monkeypatch.setattr(builtins, "__import__", fake_import)
    try:
        module = importlib.import_module("sera_ig.tui")
        assert module.curses_available() is False
        with pytest.raises(SeraError) as excinfo:
            module.run_chat(object())
        assert "curses" in str(excinfo.value)
        assert "windows-curses" in str(excinfo.value)
    finally:
        for name in [n for n in sys.modules if n.startswith("sera_ig.tui")]:
            del sys.modules[name]
        importlib.import_module("sera_ig.tui")
