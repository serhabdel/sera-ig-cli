"""Tests for the Textual application.

These run the application headless, exactly as it runs on a terminal, and
drive it with synthetic key presses and mouse clicks.
"""

from __future__ import annotations

import pytest

from sera_ig.app.main import SeraApp

from .fakes import FakeClient


@pytest.fixture
def client() -> FakeClient:
    return FakeClient()


async def wait_for(predicate, pilot, timeout: float = 5.0) -> bool:
    """Wait until *predicate* is true, pumping the event loop."""
    import asyncio

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        if predicate():
            return True
        await pilot.pause(0.05)
    return predicate()


async def test_the_app_starts(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        assert app.is_running
        assert app.query_one("#tabs")
        await pilot.pause()


async def test_every_panel_is_present(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        for name in ("chats", "feed", "stories", "notifications", "settings"):
            assert app.query_one(f"#tabs TabPane#{name}")
        await pilot.pause()


async def test_the_conversation_list_loads(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        loaded = await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)
        assert loaded
        assert len(app.query_one("#conversation-list").children) == 3
        await pilot.pause()


async def test_clicking_a_conversation_opens_it(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)
        await pilot.click("#conversation-item-0")
        opened = await wait_for(
            lambda: len(app.query_one("#message-list").children) > 0, pilot
        )
        assert opened
        await pilot.pause()


async def test_the_action_bar_appears_when_a_message_is_selected(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)
        await pilot.click("#conversation-item-0")
        await wait_for(lambda: len(app.query_one("#message-list").children) > 0, pilot)

        bubbles = app.query("#message-list MessageBubble")
        assert bubbles
        await pilot.click("#message-list MessageBubble")
        assert app.query_one("#action-bar").has_class("visible")
        await pilot.pause()


async def test_the_theme_can_be_switched(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        before = app.theme
        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme != before


async def test_setting_a_theme_persists_it(app: SeraApp, config) -> None:
    async with app.run_test() as pilot:
        app.set_theme("nord")
        await pilot.pause()
        assert app.theme == "nord"
        assert config.get("ui.theme") == "nord"


async def test_the_command_palette_opens(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        await pilot.press("ctrl+p")
        await pilot.pause()
        from textual.command import CommandPalette

        assert CommandPalette.is_open(app)
        await pilot.press("escape")
        await pilot.pause()


async def test_toggling_the_avatars_persists(app: SeraApp, config) -> None:
    async with app.run_test() as pilot:
        before = app.show_avatars
        app.toggle_avatars()
        await pilot.pause()
        assert app.show_avatars is not before
        assert config.get("ui.show_avatars") is not before


async def test_the_settings_screen_lists_the_themes(app: SeraApp) -> None:
    async with app.run_test() as pilot:
        from textual.widgets import Select

        select = app.query_one("#theme-select", Select)
        assert len(select._options) > 5
        await pilot.pause()


async def test_a_failing_fetch_keeps_the_app_alive(app: SeraApp, monkeypatch) -> None:
    """A failed refresh must never take the application down."""
    from sera_ig import api
    from sera_ig.app.chat import ChatPanel

    async with app.run_test() as pilot:
        await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)

        def boom(*args, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(api, "list_threads", boom)

        panel = app.query_one(ChatPanel)
        panel.load_conversations()

        failed = await wait_for(
            lambda: "network down" in str(panel.query_one("#chat-status").render()),
            pilot,
        )
        assert failed
        assert app.is_running
        await pilot.pause()


async def test_rerendering_the_messages_does_not_collide(app: SeraApp) -> None:
    """A refresh landing on a pending render must not duplicate the widgets.

    Textual defers both removing and mounting widgets, so a second render
    that does not wait for the first one leaves two bubbles with the same
    id, and the application crashes.
    """
    from sera_ig.app.chat import ChatPanel

    async with app.run_test() as pilot:
        await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)
        await pilot.click("#conversation-item-0")
        await wait_for(lambda: len(app.query_one("#message-list").children) > 0, pilot)

        panel = app.query_one(ChatPanel)
        messages = list(panel.messages)
        assert messages

        await panel._apply_messages(messages)
        await panel._apply_messages(messages)

        assert len(app.query_one("#message-list").children) == len(messages)
        assert app.is_running
        await pilot.pause()


async def test_a_repeated_message_is_only_shown_once(app: SeraApp) -> None:
    """Instagram can repeat a message; showing it twice would collide."""
    from sera_ig.app.chat import ChatPanel

    async with app.run_test() as pilot:
        await wait_for(lambda: len(app.query_one("#conversation-list").children) > 0, pilot)
        await pilot.click("#conversation-item-0")
        await wait_for(lambda: len(app.query_one("#message-list").children) > 0, pilot)

        panel = app.query_one(ChatPanel)
        messages = list(panel.messages)
        assert messages

        await panel._apply_messages(messages + messages)

        assert len(app.query_one("#message-list").children) == len(messages)
        assert app.is_running
        await pilot.pause()
