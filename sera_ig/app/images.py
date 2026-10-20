"""Images in the terminal: protocol detection, avatars and thumbnails.

The terminal cannot show an image everywhere, and every terminal that can
speaks a different protocol. This module picks a protocol, and degrades to
something readable when the terminal cannot do better.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

#: Every protocol the app knows about. ``auto`` is resolved at runtime.
PROTOCOLS = ("auto", "ascii", "halfblock", "braille", "kitty", "iterm2", "sixel", "none")

#: The palette used for the coloured initial-letter avatars. Chosen to stay
#: readable on both light and dark backgrounds.
AVATAR_COLORS = (
    "#E06C75",
    "#98C379",
    "#E5C07B",
    "#61AFEF",
    "#C678DD",
    "#56B6C2",
    "#D19A66",
    "#E06C9F",
)


def detect_protocol(environ: dict[str, str] | None = None) -> str:
    """Return the image protocol the current terminal supports.

    ``auto`` resolves to ``kitty`` in Kitty and WezTerm, ``iterm2`` in
    iTerm2, and ``halfblock`` everywhere else — the half-block renderer works
    in every terminal that can show colour, and needs no special support.
    """
    env = environ if environ is not None else os.environ

    if env.get("KITTY_WINDOW_ID"):
        return "kitty"
    term_program = env.get("TERM_PROGRAM", "").lower()
    if "iterm" in term_program:
        return "iterm2"
    if "wezterm" in term_program:
        return "kitty"
    if "ghostty" in term_program:
        return "kitty"
    if "kitty" in env.get("TERM", "").lower():
        return "kitty"
    return "halfblock"


def resolve_protocol(setting: str, environ: dict[str, str] | None = None) -> str:
    """Turn the configured protocol into the one to actually use."""
    value = (setting or "auto").strip().lower()
    if value not in PROTOCOLS:
        return "halfblock"
    if value == "auto":
        return detect_protocol(environ)
    return value


def supports_images(protocol: str) -> bool:
    """Whether *protocol* can actually draw an image."""
    return protocol not in ("none", "ascii")


def avatar_color(username: str | None) -> str:
    """Return a stable colour for a username.

    The same username always gets the same colour, on every machine, without
    storing anything.
    """
    name = (username or "").strip().lower() or "?"
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    return AVATAR_COLORS[digest[0] % len(AVATAR_COLORS)]


def avatar_initial(username: str | None) -> str:
    """Return the letter shown in an avatar."""
    name = (username or "").strip()
    if not name:
        return "?"
    return name[0].upper()


def avatar_text(username: str | None, enabled: bool = True) -> Any:
    """Return a Rich renderable for an avatar.

    A coloured initial letter: no network request, so the conversation list
    never waits on a profile picture.
    """
    from rich.text import Text

    if not enabled:
        return Text("")
    letter = avatar_initial(username)
    return Text(f" {letter} ", style=f"bold black on {avatar_color(username)}")


def render_image(
    data: bytes,
    width: int,
    protocol: str = "halfblock",
    height: int | None = None,
) -> Any | None:
    """Render image bytes for the terminal.

    Returns ``None`` when the protocol cannot draw images or the data cannot
    be decoded, so the caller can fall back to a placeholder.
    """
    if not supports_images(protocol) or not data:
        return None

    try:
        from io import BytesIO

        from PIL import Image
    except ImportError:  # pragma: no cover - optional at runtime
        return None

    try:
        image = Image.open(BytesIO(data)).convert("RGB")
    except Exception:
        return None

    width = max(8, int(width))
    if height is None:
        height = max(2, width // 3)

    try:
        if protocol == "braille":
            return render_braille(image, width, height)
        if protocol == "ascii":
            from rich_pixels import FullcellRenderer, Pixels

            return Pixels.from_image(
                image, resize=(width, height), renderer=FullcellRenderer()
            )
        if protocol == "halfblock":
            from rich_pixels import HalfcellRenderer, Pixels

            return Pixels.from_image(
                image, resize=(width * 2, height * 2), renderer=HalfcellRenderer()
            )
        # kitty, iterm2 and sixel need a terminal-specific escape sequence
        # that rich-pixels does not emit; the caller shows a placeholder.
        return None
    except Exception:  # pragma: no cover - rendering is best effort
        return None


#: The bit each dot of a braille cell carries.
_BRAILLE_DOTS = (
    (0, 0, 0x01),
    (0, 1, 0x02),
    (0, 2, 0x04),
    (1, 0, 0x08),
    (1, 1, 0x10),
    (1, 2, 0x20),
    (0, 3, 0x40),
    (1, 3, 0x80),
)


def render_braille(image: Any, width: int, height: int) -> Any:
    """Render a PIL image as braille characters.

    Each character carries a 2×4 grid of dots, so the result is four times
    taller than it looks — which is why the image is resized accordingly.
    """
    from PIL import Image
    from rich.text import Text

    resized = image.resize((width * 2, height * 4), Image.LANCZOS).convert("L")
    pixels = resized.load()
    lines: list[str] = []
    for row in range(height):
        cells: list[str] = []
        for column in range(width):
            bits = 0
            for x, y, bit in _BRAILLE_DOTS:
                pixel_x = column * 2 + x
                pixel_y = row * 4 + y
                if pixel_x < resized.width and pixel_y < resized.height:
                    if pixels[pixel_x, pixel_y] < 128:
                        bits |= bit
            cells.append(chr(0x2800 + bits) if bits else " ")
        lines.append("".join(cells))
    return Text("\n".join(lines))


def cache_dir(config: Any = None) -> Any:
    """Return the directory used to cache downloaded avatars."""
    from ..config import get_config

    config = config or get_config()
    path = config.data_dir / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path
