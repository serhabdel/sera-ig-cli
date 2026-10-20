"""Snapshot tests for the application.

The screens are exported as SVG, exactly as a user would see them, and
compared with the files in ``tests/snapshots``. The first run writes the
baseline; delete a file to record a new one.

These are deliberately few and small: enough to catch a layout that broke,
not so many that a harmless colour change fails the build.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sera_ig.app.main import SeraApp

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


async def settle(app: SeraApp, pilot, timeout: float = 5.0) -> None:
    """Wait for the panels to finish loading."""
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if app.query_one("#conversation-list").children:
            break
        await pilot.pause(0.05)
    await pilot.pause(0.2)


def compare(name: str, svg: str) -> None:
    """Compare *svg* with the stored snapshot, writing it when it is missing."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    target = SNAPSHOT_DIR / f"{name}.svg"
    if not target.exists():
        target.write_text(svg, encoding="utf-8")
        pytest.skip(f"wrote the baseline snapshot {target.name}")
    assert target.read_text(encoding="utf-8") == svg, (
        f"{target.name} changed. Delete it to record a new snapshot."
    )


async def test_the_chats_screen(app: SeraApp) -> None:
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        compare("chats", app.export_screenshot())


async def test_the_settings_screen(app: SeraApp) -> None:
    async with app.run_test(size=(120, 40)) as pilot:
        await settle(app, pilot)
        app.goto_screen("settings")
        await pilot.pause(0.3)
        compare("settings", app.export_screenshot())
