"""Shared pytest fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from sera_ig import config as config_module
from sera_ig.state import reset_state


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SERA_IG_HOME`` at a throw-away directory for every test."""
    home = tmp_path / "sera-home"
    monkeypatch.setenv("SERA_IG_HOME", str(home))
    config_module.reset_config_cache()
    reset_state()
    yield home
    config_module.reset_config_cache()
    reset_state()


@pytest.fixture
def config():
    """A fresh config bound to the isolated home."""
    return config_module.get_config()


@pytest.fixture
def fake_client():
    """A stand-in for the instagrapi client."""
    from .fakes import FakeClient

    return FakeClient()


@pytest.fixture
def app(fake_client):
    """The application, wired to the fake client."""
    from sera_ig.app.main import SeraApp

    return SeraApp(fake_client)
