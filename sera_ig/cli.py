"""The ``seraig`` command line interface."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

import typer

from . import __version__
from .client import SessionManager, connect
from .commands import auth as auth_cmds
from .commands import chat as chat_cmds
from .commands import feed as feed_cmds
from .commands import media as media_cmds
from .commands import notify as notify_cmds
from .commands import stories as stories_cmds
from .commands import user as user_cmds
from .config import get_config
from .errors import SeraError
from .output import console, fail, ok
from .state import resolve_output, set_state

logger = logging.getLogger("sera_ig")

app = typer.Typer(
    name="seraig",
    help=(
        "Instagram in your terminal.\n\n"
        "A private-API Instagram client built on instagrapi — chat, feed, stories "
        "and notifications without opening a browser."
    ),
    add_completion=True,
    no_args_is_help=False,
    rich_markup_mode="rich",
)

tui_app = typer.Typer(no_args_is_help=True, help="Interactive terminal interfaces.")


# --------------------------------------------------------------------- banner
def print_banner() -> None:
    """Print the splash screen."""
    try:
        from art import text2art

        logo = text2art("SeraIG", font="standard")
    except Exception:  # pragma: no cover - art is optional at runtime
        logo = r"""
   _____ _____ ______ _____ _    __
  / ____|_   _|  ____|  _ \ |  / /
 | (___   | | | |__  | |_) || / /
  \___ \  | | |  __| |  _ < |/ /
  ____) |_| |_| |____| |_) |
 |_____/\___/ \_____|_/____/
"""
    console.print(f"[magenta]{logo}[/magenta]")
    console.print("[green]The end of brainrot and doomscrolling is here.[/green]")
    console.print()
    console.print("Type [cyan]help[/cyan] for the commands, [cyan]exit[/cyan] to leave the shell.")
    console.print(
        "[dim]Pro tip: use the --output json flag for scripting and AI agents.[/dim]"
    )


# ---------------------------------------------------------------- root command
@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    account: str = typer.Option(
        None, "--account", "-a", help="Which saved account to use for this run"
    ),
    output: str = typer.Option(
        None, "-o", "--output", help="Output format: text (default) or json"
    ),
    version: bool = typer.Option(
        False, "--version", "-v", help="Show the version and exit", is_eager=True
    ),
    shell: bool = typer.Option(
        False, "--shell", "-s", help="Open the interactive shell", is_eager=True
    ),
) -> None:
    """Instagram in your terminal."""
    if version:
        console.print(f"sera-ig-cli {__version__}")
        raise typer.Exit()

    if output is not None:
        lowered = output.strip().lower()
        if lowered not in ("text", "json"):
            raise typer.BadParameter("Output format must be 'text' or 'json'.")
        set_state(output=lowered)
    if account:
        set_state(account=account.lstrip("@").strip())

    _setup_logging()

    if shell:
        _open_shell()
        raise typer.Exit()

    if ctx.invoked_subcommand is not None:
        return

    # No subcommand: greet and drop into the interactive shell.
    print_banner()
    _open_shell()


def _open_shell() -> None:
    """Start the interactive shell."""
    from .shell import run as run_shell

    run_shell()


def _setup_logging() -> None:
    """Send debug logs to a file when debugging is switched on."""
    config = get_config()
    if not config.get("advanced.debug"):
        return
    logs = config.logs_dir
    logs.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(logs / "sera-ig.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    root_logger = logging.getLogger("sera_ig")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(handler)
    logging.getLogger("instagrapi").setLevel(logging.DEBUG)


# ----------------------------------------------------------------- auth group
app.add_typer(auth_cmds.app, name="auth", help="Sign in, sign out and manage accounts.")


# ------------------------------------------------------------------ tui group
@tui_app.command("chat")
def tui_chat(
    thread: str = typer.Argument(None, help="Open straight into this conversation"),
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
) -> None:
    """Open the interactive chat interface."""
    from .tui import run_chat

    with connect(account or None) as client:
        run_chat(client, thread)


@tui_app.command("feed")
def tui_feed(
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
) -> None:
    """Open the interactive feed browser."""
    from .tui import run_feed

    with connect(account or None) as client:
        run_feed(client)


app.add_typer(tui_app, name="tui", help="Interactive terminal interfaces.")


# ------------------------------------------------------------- direct messages
app.command("inbox", help="List your direct-message conversations.")(chat_cmds.inbox)
app.command("read", help="Read the messages of a conversation.")(chat_cmds.read)
app.command("send", help="Send a message to a conversation.")(chat_cmds.send)
app.command("reply", help="Reply to a specific message.")(chat_cmds.reply)
app.command("react", help="React to a message with an emoji.")(chat_cmds.react)
app.command("unsend", help="Unsend a message you sent.")(chat_cmds.unsend)
app.command("seen", help="Mark a conversation as read.")(chat_cmds.seen)
app.command("search", help="Search Instagram for people.")(chat_cmds.search)
app.command("download-message", help="Download the media attached to a message.")(
    chat_cmds.download
)


# ------------------------------------------------------------------- browsing
app.command("feed", help="Show posts from the people you follow.")(feed_cmds.feed)
app.command("reels", help="Show reels.")(feed_cmds.reels)
app.command("stories", help="Show stories from the people you follow.")(stories_cmds.stories)
app.command("notify", help="Show recent activity.")(notify_cmds.notify)


# --------------------------------------------------------------------- people
app.command("user", help="Show a profile summary.")(user_cmds.user)
app.command("posts", help="Show the latest posts of an account.")(user_cmds.posts)
app.command("followers", help="Show the followers of an account.")(user_cmds.followers)
app.command("following", help="Show the accounts an account follows.")(user_cmds.following)


# ---------------------------------------------------------------------- media
app.command("post", help="Show the details of a post.")(media_cmds.info)
app.command("like", help="Like a post.")(media_cmds.like)
app.command("comment", help="Comment on a post.")(media_cmds.comment)
app.command("comments", help="List the comments of a post.")(media_cmds.comments)
app.command("download", help="Download a photo or video.")(media_cmds.download)


# --------------------------------------------------------------------- config
@app.command("config", help="Read and write the configuration.")
def config_command(
    action: str = typer.Argument(
        None, help="get, set, list, edit or reset"
    ),
    key: str = typer.Argument(None, help="Configuration key, e.g. chat.page_size"),
    value: str = typer.Argument(None, help="Value to set"),
    edit: bool = typer.Option(False, "--edit", help="Open the config file in $EDITOR"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Manage the configuration stored in ``~/.sera-ig-cli/config.yaml``."""
    from .output import emit, print_rows
    from .state import resolve_output

    fmt = resolve_output(output)
    cfg = get_config()

    if edit or action == "edit":
        editor = os.environ.get("EDITOR", "nano")
        os.system(f'{editor} "{cfg.path}"')
        cfg.load()
        ok("Configuration reloaded.")
        return

    if action == "list":
        records = [{"key": k, "value": _redact(k, v)} for k, v in cfg.items()]
        emit(fmt, records, lambda: print_rows(records, ["key", "value"]))
        return

    if action == "get":
        if not key:
            raise typer.BadParameter("Provide a key: seraig config get <key>")
        current = cfg.get(key)
        if current is None:
            emit(
                fmt,
                {"key": key, "value": None},
                lambda: console.print(f"[yellow]Key '{key}' is not set.[/yellow]"),
            )
            raise typer.Exit(code=1)
        emit(
            fmt,
            {"key": key, "value": _redact(key, current)},
            lambda: console.print(f"{key} = {_redact(key, current)}"),
        )
        return

    if action == "set":
        if not key or value is None:
            raise typer.BadParameter(
                "Provide a key and a value: seraig config set <key> <value>"
            )
        cfg.set(key, _coerce(value))
        emit(
            fmt,
            {"key": key, "value": cfg.get(key)},
            lambda: ok(f"{key} = {cfg.get(key)}"),
        )
        return

    if action == "reset":
        cfg.reset()
        emit(
            fmt,
            {"reset": True},
            lambda: ok("Configuration reset to defaults."),
        )
        return

    raise typer.BadParameter("Usage: seraig config [get|set|list|edit|reset]")


def _redact(key: str, value: Any) -> Any:
    """Hide secrets when a configuration value is printed."""
    lowered = key.lower()
    if any(word in lowered for word in ("secret", "password", "token", "key")) and value:
        return "***"
    return value


def _coerce(raw: str) -> Any:
    """Turn a string from the command line into a typed value."""
    lowered = raw.strip().lower()
    if lowered in ("true", "yes", "on"):
        return True
    if lowered in ("false", "no", "off"):
        return False
    if lowered in ("null", "none", ""):
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


# -------------------------------------------------------------------- version
@app.command("version", help="Show the version.")
def version_command() -> None:
    """Print the version."""
    console.print(f"sera-ig-cli {__version__}")


@app.command("shell", help="Open the interactive shell.")
def shell_command(
    account: str = typer.Option(None, "--account", "-a", help="Account to use"),
) -> None:
    """Open the interactive shell."""
    if account:
        set_state(account=account.lstrip("@").strip())
    _open_shell()


# --------------------------------------------------------------------- theme
theme_app = typer.Typer(no_args_is_help=True, help="List, set and inspect themes.")


@theme_app.command("list")
def theme_list(
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """List every available theme."""
    from .app.themes import builtin_themes, user_themes
    from .output import dump_json, print_rows

    fmt = resolve_output(output)
    current = get_config().get("ui.theme")
    builtins = sorted(builtin_themes())
    users = sorted(user_themes())
    records = [
        {"name": name, "source": "builtin", "active": name == current}
        for name in builtins
    ] + [
        {"name": name, "source": "user", "active": name == current}
        for name in users
    ]
    if fmt == "json":
        dump_json(records)
        return
    print_rows(records, ["name", "source", "active"])


@theme_app.command("set")
def theme_set(
    name: str = typer.Argument(..., help="Theme to use"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Set the theme used by the application."""
    from .app.themes import resolve_theme
    from .output import dump_json

    fmt = resolve_output(output)
    if resolve_theme(name) is None:
        raise typer.BadParameter(
            f"No theme called '{name}'. Run `seraig theme list` to see the available ones."
        )
    get_config().set("ui.theme", name)
    payload = {"theme": name, "active": True}
    if fmt == "json":
        dump_json(payload)
        return
    ok(f"Theme set to '{name}'")


@theme_app.command("show")
def theme_show(
    name: str = typer.Argument(None, help="Theme to describe (defaults to the current one)"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show the colours of a theme."""
    from .app.themes import theme_summary
    from .output import dump_json, print_table

    fmt = resolve_output(output)
    target = name or get_config().get("ui.theme")
    summary = theme_summary(target)
    if summary is None:
        raise typer.BadParameter(f"No theme called '{target}'.")
    if fmt == "json":
        dump_json(summary)
        return
    rows = [(key, value) for key, value in summary.items() if key != "variables"]
    print_table(rows, ["setting", "value"])
    if summary["variables"]:
        console.print("[bold]variables[/bold]")
        print_table(
            [(key, value) for key, value in summary["variables"].items()],
            ["name", "value"],
        )


app.add_typer(theme_app, name="theme", help="List, set and inspect themes.")


# --------------------------------------------------------------------- doctor
@app.command("doctor", help="Check the installation and the stored sessions.")
def doctor() -> None:
    """Show a quick health check of the installation."""
    config = get_config()
    manager = SessionManager()
    accounts = manager.accounts()
    console.print(f"[bold]sera-ig-cli[/bold] {__version__}")
    console.print(f"config      {config.path}")
    console.print(f"data dir    {config.data_dir}")
    for name in accounts:
        path = config.session_path(name)
        exists = path.exists()
        size = f"{path.stat().st_size} bytes" if exists else "missing"
        console.print(f"session     {path}  [dim]({size})[/dim]")
    if not accounts:
        console.print("sessions    none — run `seraig auth login`")
    console.print(
        "[dim]Reinstalling the package never touches these files: "
        "the session lives in the data dir, not in the program directory.[/dim]"
    )
    try:
        import instagrapi

        console.print(f"instagrapi  {getattr(instagrapi, '__version__', 'installed')}")
    except Exception:  # pragma: no cover - dependency missing
        console.print("[red]instagrapi is not installed[/red]")


# ------------------------------------------------------------------ entrypoint
def run_command_line(args: list[str]) -> int:
    """Run one command programmatically and return its exit code.

    This is what the interactive shell uses, so a command behaves exactly the
    same whether it is typed at the prompt or on the command line.
    """
    from .click_compat import click_module

    click = click_module()
    command = typer.main.get_command(app)
    try:
        command.main(args=args, prog_name="seraig", standalone_mode=False)
    except typer.Exit as exc:
        return int(getattr(exc, "exit_code", 0) or 0)
    except typer.Abort:
        console.print("\n[dim]Interrupted.[/dim]")
        return 130
    except click.ClickException as exc:
        exc.show()
        return int(getattr(exc, "exit_code", 1) or 1)
    except SeraError as exc:
        fail(str(exc))
        return exc.exit_code
    except SystemExit as exc:  # pragma: no cover - defensive
        return int(exc.code or 0)
    return 0


def main() -> None:
    """The ``seraig`` console script entry point."""
    try:
        app()
    except SeraError as exc:
        fail(str(exc))
        sys.exit(exc.exit_code)
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
        sys.exit(130)
    except Exception as exc:  # pragma: no cover - last resort
        from .errors import translate

        translated = translate(exc)
        fail(str(translated))
        if os.environ.get("SERA_IG_DEBUG"):
            raise
        sys.exit(translated.exit_code)


if __name__ == "__main__":  # pragma: no cover
    main()
