"""Process-wide CLI state (the account in use and the output format)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppState:
    """Options shared by every command."""

    account: str | None = None
    output: str = "text"
    extra: dict[str, object] = field(default_factory=dict)


_state = AppState()


def get_state() -> AppState:
    """Return the global state object."""
    return _state


def set_state(**kwargs: object) -> AppState:
    """Update the global state and return it."""
    for key, value in kwargs.items():
        if hasattr(_state, key):
            setattr(_state, key, value)
    return _state


def reset_state() -> AppState:
    """Reset the global state — used by tests."""
    global _state
    _state = AppState()
    return _state


def resolve_account(local: str | None = None) -> str | None:
    """Return the account to use: the command-local one wins over the global."""
    if local:
        return local.lstrip("@").strip()
    return get_state().account


def resolve_output(local: str | None = None) -> str:
    """Return the output format: the command-local one wins over the global."""
    return local or get_state().output
