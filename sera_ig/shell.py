"""The interactive shell.

``seraig`` (or ``seraig shell``) drops into a prompt where every command is
available without repeating the program name::

    seraig ❯ inbox
    seraig ❯ read noor
    seraig ❯ send noor --text "hi"

History, tab completion for commands *and* their options, and a hint line
make it feel like a real console rather than a list of subcommands.
"""

from __future__ import annotations

import os
import shlex
from typing import Any

from .click_compat import click_module
from .config import get_config
from .errors import SeraError
from .output import console
from .state import get_state

try:  # pragma: no cover - depends on the installation
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.shortcuts import PromptSession

    PROMPT_TOOLKIT_ERROR: ImportError | None = None
except ImportError as exc:  # pragma: no cover - optional at runtime
    PROMPT_TOOLKIT_ERROR = exc
    Completer = object  # type: ignore[assignment,misc]
    Completion = None  # type: ignore[assignment]
    FileHistory = None  # type: ignore[assignment]
    patch_stdout = None  # type: ignore[assignment]
    PromptSession = None  # type: ignore[assignment]

BANNER_COMMANDS = {"help", "?", "h"}
EXIT_COMMANDS = {"exit", "quit", "q"}


def _click_module() -> Any:
    """Return click, whether it is standalone or vendored inside typer."""
    return click_module()


def _command_paths() -> dict[tuple[str, ...], Any]:
    """Map every command path to its click command object."""
    from typer.main import get_command

    from .cli import app

    root = get_command(app)
    found: dict[tuple[str, ...], Any] = {}

    def walk(command: Any, prefix: tuple[str, ...]) -> None:
        found[prefix] = command
        for name, sub in getattr(command, "commands", {}).items():
            walk(sub, prefix + (name,))

    walk(root, ())
    return found


def _options_of(command: Any) -> list[str]:
    """Return the option strings a command accepts."""
    options: list[str] = []
    for param in command.get_params(_click_module().Context(command)):
        options.extend(param.opts)
        options.extend(param.secondary_opts)
    return options


class ShellCompleter(Completer):
    """Completes command names, subcommands and options."""

    def __init__(self, paths: dict[tuple[str, ...], Any]) -> None:
        self.paths = paths
        self._names = sorted({path[0] for path in paths if path})

    def get_completions(self, document: Any, complete_event: Any) -> list[Completion]:
        text = document.text_before_cursor
        words = text.split()
        trailing = text.endswith(" ")
        completed = words if trailing else words[:-1]
        current = "" if trailing else (words[-1] if words else "")

        # The deepest command path built from the words already finished.
        path: tuple[str, ...] = ()
        for word in completed:
            if path + (word,) in self.paths:
                path = path + (word,)
            else:
                break

        command = self.paths.get(path)

        # Subcommands win over options.
        subcommands = sorted(getattr(command, "commands", {}))
        if subcommands:
            return [
                Completion(name, start_position=-len(current))
                for name in subcommands
                if name.startswith(current)
            ]

        # Otherwise offer the options of the command.
        if command is None:
            return [
                Completion(name, start_position=-len(current))
                for name in self._names
                if name.startswith(current)
            ]

        return [
            Completion(option, start_position=-len(current))
            for option in _options_of(command)
            if option.startswith(current)
        ]


def _print_help() -> None:
    """Show the shell's own help."""
    console.print("[bold magenta]seraig shell[/bold magenta]")
    console.print()
    console.print("Type a command without the program name — [cyan]inbox[/cyan], [cyan]read noor[/cyan], …")
    console.print("Prefix it with [cyan]seraig[/cyan] if you prefer: [cyan]seraig inbox[/cyan].")
    console.print()
    console.print("  [cyan]help[/cyan]      this message")
    console.print("  [cyan]clear[/cyan]     clear the screen")
    console.print("  [cyan]tui chat[/cyan]  open the full-screen chat interface")
    console.print("  [cyan]exit[/cyan]      leave the shell")
    console.print()
    console.print("Tab completes command names and options. [cyan]-o json[/cyan] works everywhere.")


def _needs_terminal(args: list[str]) -> bool:
    """Whether the command takes over the whole terminal."""
    return bool(args) and args[0] in ("tui", "app")


def run(args: list[str] | None = None) -> int:
    """Run the interactive shell."""
    if PROMPT_TOOLKIT_ERROR is not None:  # pragma: no cover - optional at runtime
        raise SeraError(
            "The interactive shell needs prompt_toolkit. "
            "Install it with: pip install prompt_toolkit"
        )

    from .cli import run_command_line

    config = get_config()
    history_path = config.data_dir / "history"
    try:
        history_path.parent.mkdir(parents=True, exist_ok=True)
        history = FileHistory(str(history_path))
    except OSError:  # pragma: no cover - unwritable home
        history = None

    paths = _command_paths()
    session: PromptSession = PromptSession(
        history=history,
        completer=ShellCompleter(paths),
        complete_while_typing=True,
        enable_history_search=True,
    )
    # Some terminals never answer a cursor-position request; the warning is
    # noise in the middle of a session, and the shell works fine without it.
    # The renderer holds the callback, so it has to be silenced there.
    try:
        session.app.renderer.cpr_not_supported_callback = lambda: None
    except AttributeError:  # pragma: no cover - prompt_toolkit internals
        pass

    console.print("[dim]Type [cyan]help[/cyan] for the commands, [cyan]exit[/cyan] to leave.[/dim]")

    while True:
        account = get_state().account or config.get("login.current_username")
        prompt = f"seraig(@{account}) ❯ " if account else "seraig ❯ "
        try:
            with patch_stdout():
                line = session.prompt(prompt)
        except KeyboardInterrupt:
            console.print("[dim]Use Ctrl-D or type 'exit' to leave.[/dim]")
            continue
        except EOFError:
            console.print()
            return 0

        line = (line or "").strip()
        if not line:
            continue

        try:
            parts = shlex.split(line)
        except ValueError as exc:
            console.print(f"[red]Could not parse that: {exc}[/red]")
            continue

        if parts and parts[0] == "seraig":
            parts = parts[1:]
        if not parts:
            continue

        command = parts[0].lower()
        if command in EXIT_COMMANDS:
            console.print("[dim]Bye.[/dim]")
            return 0
        if command in {"clear", "cls"}:
            os.system("cls" if os.name == "nt" else "clear")
            continue
        if command in BANNER_COMMANDS:
            _print_help()
            continue

        try:
            if _needs_terminal(parts):
                _run_fullscreen(session, parts, run_command_line)
            else:
                with patch_stdout():
                    run_command_line(parts)
        except SeraError as exc:
            console.print(f"[red]✗[/red] {exc}")
        except Exception as exc:  # pragma: no cover - last resort
            console.print(f"[red]✗[/red] {type(exc).__name__}: {exc}")


def _run_fullscreen(session: Any, args: list[str], run_command_line: Any) -> None:
    """Run a command that takes over the terminal."""
    from .errors import translate

    def target() -> int:
        return run_command_line(args)

    def done() -> None:
        return None

    try:
        session.app.run_in_terminal(target, done)
    except Exception as exc:  # pragma: no cover - terminal dependent
        translated = translate(exc)
        console.print(f"[red]✗[/red] {translated}")
