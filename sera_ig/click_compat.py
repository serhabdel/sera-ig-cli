"""Access to click, whichever way it is installed.

typer vendors click as ``typer._click`` in recent releases and depends on
the standalone ``click`` package in older ones. This module hides the
difference so nothing else has to care.
"""

from __future__ import annotations

from typing import Any


def click_module() -> Any:
    """Return the click module, standalone or vendored inside typer."""
    try:  # pragma: no cover - depends on the typer version
        import click

        return click
    except ImportError:  # pragma: no cover
        from typer import _click

        return _click
