"""sera-ig-cli — Instagram in your terminal.

A terminal client for Instagram built on top of the private mobile API via
`instagrapi <https://github.com/subzeroid/instagrapi>`_.

The project is unofficial and not affiliated with Meta or Instagram.
"""

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

try:
    __version__ = _version("sera-ig-cli")
except PackageNotFoundError:  # pragma: no cover - running from a source tree
    __version__ = "0.5.0"

__all__ = ["__version__"]
