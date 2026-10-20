"""Tests for the image helpers."""

from __future__ import annotations

import pytest

from sera_ig.app.images import (
    AVATAR_COLORS,
    PROTOCOLS,
    avatar_color,
    avatar_initial,
    avatar_text,
    detect_protocol,
    render_image,
    resolve_protocol,
    supports_images,
)


def test_detects_kitty_from_the_window_id() -> None:
    assert detect_protocol({"KITTY_WINDOW_ID": "1"}) == "kitty"


def test_detects_iterm() -> None:
    assert detect_protocol({"TERM_PROGRAM": "iTerm.app"}) == "iterm2"


def test_detects_wezterm() -> None:
    assert detect_protocol({"TERM_PROGRAM": "WezTerm"}) == "kitty"


def test_detects_kitty_from_the_terminal_name() -> None:
    assert detect_protocol({"TERM": "xterm-kitty"}) == "kitty"


def test_falls_back_to_halfblock() -> None:
    assert detect_protocol({}) == "halfblock"
    assert detect_protocol({"TERM": "xterm-256color"}) == "halfblock"


def test_auto_resolves_to_the_detected_protocol() -> None:
    assert resolve_protocol("auto", {"KITTY_WINDOW_ID": "1"}) == "kitty"
    assert resolve_protocol("auto", {}) == "halfblock"


def test_an_explicit_protocol_is_kept() -> None:
    assert resolve_protocol("braille", {"KITTY_WINDOW_ID": "1"}) == "braille"


def test_an_unknown_protocol_falls_back() -> None:
    assert resolve_protocol("nonsense", {}) == "halfblock"


def test_protocols_are_listed() -> None:
    for protocol in ("auto", "ascii", "halfblock", "braille", "kitty", "iterm2", "sixel", "none"):
        assert protocol in PROTOCOLS


def test_none_and_ascii_cannot_draw_images() -> None:
    assert supports_images("none") is False
    assert supports_images("ascii") is False
    assert supports_images("halfblock") is True
    assert supports_images("kitty") is True


def test_avatar_colour_is_deterministic() -> None:
    assert avatar_color("abdel") == avatar_color("abdel")
    assert avatar_color("abdel") in AVATAR_COLORS


def test_avatar_colour_differs_between_users() -> None:
    colours = {avatar_color(f"user{index}") for index in range(20)}
    assert len(colours) > 1


def test_avatar_colour_handles_an_empty_name() -> None:
    assert avatar_color("") in AVATAR_COLORS
    assert avatar_color(None) in AVATAR_COLORS


def test_avatar_initial() -> None:
    assert avatar_initial("abdel") == "A"
    assert avatar_initial("") == "?"
    assert avatar_initial(None) == "?"


def test_avatar_text_can_be_switched_off() -> None:
    assert str(avatar_text("abdel", enabled=False)) == ""
    assert "A" in str(avatar_text("abdel"))


def test_render_image_rejects_undecodable_data() -> None:
    assert render_image(b"not an image", 20, "halfblock") is None


def test_render_image_rejects_protocols_that_cannot_draw() -> None:
    assert render_image(b"\x89PNG", 20, "none") is None


def test_render_image_returns_none_for_empty_data() -> None:
    assert render_image(b"", 20, "halfblock") is None


def test_render_image_renders_a_real_image() -> None:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 40), (200, 30, 60)).save(buffer, format="PNG")
    rendered = render_image(buffer.getvalue(), 20, "halfblock")
    assert rendered is not None


@pytest.mark.parametrize("protocol", ["kitty", "iterm2", "sixel"])
def test_terminal_specific_protocols_fall_back_to_a_placeholder(protocol: str) -> None:
    from io import BytesIO

    from PIL import Image

    buffer = BytesIO()
    Image.new("RGB", (40, 40), (10, 20, 30)).save(buffer, format="PNG")
    assert render_image(buffer.getvalue(), 20, protocol) is None
