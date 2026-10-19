"""Authentication commands — ``seraig auth ...``."""

from __future__ import annotations

import os
import sys

import typer

from ..client import SessionManager
from ..client import login as perform_login
from ..client import logout as perform_logout
from ..output import console, dump_json, ok
from ..state import resolve_account, resolve_output

app = typer.Typer(no_args_is_help=True, help="Sign in, sign out and manage accounts.")


def _read_password(
    password: str | None,
    password_stdin: bool,
    account: str,
) -> str:
    """Find the password from the flag, the environment or an interactive prompt."""
    if password:
        return password
    env = os.environ.get("SERA_IG_PASSWORD")
    if env:
        return env
    if password_stdin:
        return sys.stdin.readline().strip()
    return typer.prompt(f"Password for @{account}", hide_input=True)


@app.command("login")
def login(
    account: str = typer.Option(None, "--account", "-a", help="Account to sign in to"),
    password: str = typer.Option(
        None, "--password", help="Password (prefer --password-stdin or the prompt)"
    ),
    password_stdin: bool = typer.Option(
        False, "--password-stdin", help="Read the password from stdin"
    ),
    code: str = typer.Option(
        "", "--code", help="Two-factor code, when you already have it"
    ),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Sign in to Instagram and store the session locally."""
    fmt = resolve_output(output)
    username = (account or "").lstrip("@").strip()
    if not username:
        username = typer.prompt("Instagram username").lstrip("@").strip()
    if not username:
        raise typer.BadParameter("An Instagram username is required.")

    secret = _read_password(password, password_stdin, username)

    client = perform_login(username, secret, verification_code=code)
    payload = {
        "account": client.username,
        "user_id": str(client.user_id),
        "logged_in": True,
    }
    if fmt == "json":
        dump_json(payload)
    else:
        ok(f"Logged in as @{client.username}")


@app.command("logout")
def logout(
    account: str = typer.Option(None, "--account", "-a", help="Account to sign out of"),
    keep_session: bool = typer.Option(
        False, "--keep-session", help="Only clear the local session, do not revoke it"
    ),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Sign out of Instagram and remove the local session."""
    fmt = resolve_output(output)
    manager = SessionManager()
    username = resolve_account(account) or manager.default_username()
    if not username:
        raise typer.BadParameter("No account is logged in.")
    perform_logout(username, manager=manager, revoke=not keep_session)
    if fmt == "json":
        dump_json({"account": username, "logged_in": False})
    else:
        ok(f"Logged out @{username}")


@app.command("switch")
def switch(
    account: str = typer.Argument(..., help="Account to make the default"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Make another saved account the default."""
    fmt = resolve_output(output)
    manager = SessionManager()
    username = account.lstrip("@").strip()
    if not manager.has_session(username):
        raise typer.BadParameter(
            f"No session found for @{username}. Run `seraig auth login --account {username}` first."
        )
    manager.config.set("login.current_username", username)
    manager.config.set("login.default_username", username)
    if fmt == "json":
        dump_json({"account": username, "switched": True})
    else:
        ok(f"Now using @{username}")


@app.command("whoami")
def whoami(
    account: str = typer.Option(None, "--account", "-a", help="Account to inspect"),
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """Show which account the CLI is using."""
    fmt = resolve_output(output)
    manager = SessionManager()
    username = resolve_account(account) or manager.default_username()
    if not username:
        if fmt == "json":
            dump_json({"account": None, "logged_in": False})
        else:
            console.print("No account is logged in. Run `seraig auth login`.")
        return
    if fmt == "json":
        dump_json({"account": username, "logged_in": manager.has_session(username)})
    else:
        console.print(f"@{username}")


@app.command("accounts")
def accounts(
    output: str = typer.Option(None, "-o", "--output", help="Output format: text or json"),
) -> None:
    """List every account with a saved session."""
    fmt = resolve_output(output)
    manager = SessionManager()
    config = manager.config
    current = config.get("login.current_username")
    names = manager.accounts()
    records = [
        {
            "account": name,
            "active": name == current,
            "session": str(config.session_path(name)),
        }
        for name in names
    ]
    if fmt == "json":
        dump_json(records)
        return
    if not records:
        console.print("No accounts yet. Run `seraig auth login`.")
        return
    from ..output import print_rows

    print_rows(records, ["account", "active", "session"])
