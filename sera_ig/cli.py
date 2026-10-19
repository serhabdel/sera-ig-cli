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
from .state import set_state

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
    console.print("Type [cyan]seraig --help[/cyan] to see the available commands.")
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

    if ctx.invoked_subcommand is not None:
        return
    print_banner()


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
    console.print(f"accounts    {', '.join('@' + a for a in accounts) if accounts else 'none'}")
    try:
        import instagrapi

        console.print(f"instagrapi  {getattr(instagrapi, '__version__', 'installed')}")
    except Exception:  # pragma: no cover - dependency missing
        console.print("[red]instagrapi is not installed[/red]")


# ------------------------------------------------------------------ entrypoint
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
