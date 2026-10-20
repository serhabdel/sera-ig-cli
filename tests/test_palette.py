"""Tests for the command palette provider."""

from __future__ import annotations

import pytest

from sera_ig.app.palette import CLI_COMMANDS, SeraProvider


@pytest.fixture
async def running(app):
    """The application, actually running."""
    async with app.run_test() as pilot:
        yield app, pilot


async def hits_for(app, query: str) -> list:
    """Return the palette hits for *query*."""
    provider = SeraProvider(app.screen)
    return [hit async for hit in provider.search(query)]


async def test_the_provider_offers_the_app_actions(running) -> None:
    app, _ = running
    hits = await hits_for(app, "")
    names = [str(getattr(hit, "text", None) or hit.display) for hit in hits]
    assert any("chats" in name.lower() for name in names)
    assert any("theme" in name.lower() for name in names)


async def test_the_provider_offers_the_cli_commands(running) -> None:
    app, _ = running
    hits = await hits_for(app, "inbox")
    assert any("seraig inbox" in str(hit.text) for hit in hits)


async def test_the_provider_matches_a_cli_command(running) -> None:
    app, _ = running
    hits = await hits_for(app, "seraig read")
    assert any("seraig read" in str(hit.text) for hit in hits)


async def test_every_cli_command_is_offered(running) -> None:
    app, _ = running
    for name in CLI_COMMANDS:
        hits = await hits_for(app, f"seraig {name}")
        assert any(f"seraig {name}" in str(hit.text) for hit in hits), name


async def test_discover_lists_the_app_actions(running) -> None:
    app, _ = running
    provider = SeraProvider(app.screen)
    hits = [hit async for hit in provider.discover()]
    assert hits
    assert any("Chats" in str(hit.display) for hit in hits)


async def test_a_hit_runs_its_action(running) -> None:
    app, _ = running
    provider = SeraProvider(app.screen)
    hits = [hit async for hit in provider.search("Quit")]
    assert hits
    # The callback must be callable without arguments.
    hits[0].command()
    assert app._exit is True
