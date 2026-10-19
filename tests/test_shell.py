"""Tests for the interactive shell."""

from __future__ import annotations

import json

from prompt_toolkit.document import Document

from sera_ig.shell import ShellCompleter, _command_paths, _options_of


def complete(text: str) -> list[str]:
    """Return the completion candidates for *text*."""
    completer = ShellCompleter(_command_paths())
    document = Document(text, len(text))
    return [c.text for c in completer.get_completions(document, None)]


def test_command_paths_include_the_main_groups() -> None:
    paths = _command_paths()
    assert ("inbox",) in paths
    assert ("auth", "login") in paths
    assert ("tui", "chat") in paths
    assert () in paths


def test_completes_top_level_commands() -> None:
    assert "inbox" in complete("inb")
    assert "read" in complete("re")
    assert "send" in complete("se")


def test_completes_nothing_for_an_unknown_prefix() -> None:
    assert complete("zzzz") == []


def test_completes_subcommands() -> None:
    candidates = complete("auth ")
    assert "login" in candidates
    assert "logout" in candidates
    assert "accounts" in candidates


def test_completes_subcommand_prefix() -> None:
    candidates = complete("auth lo")
    assert "login" in candidates
    assert "logout" in candidates
    assert "accounts" not in candidates


def test_completes_options() -> None:
    candidates = complete("inbox --li")
    assert "--limit" in candidates


def test_completes_options_after_a_space() -> None:
    candidates = complete("inbox ")
    assert "--limit" in candidates
    assert "--output" in candidates


def test_options_of_lists_both_spellings() -> None:
    paths = _command_paths()
    options = _options_of(paths[("inbox",)])
    assert "--limit" in options
    assert "-n" in options


def test_run_command_line_executes_a_command(monkeypatch, fake_client, capsys) -> None:
    """A command typed in the shell behaves exactly like one on the command line."""
    from contextlib import contextmanager

    from sera_ig import client as client_module
    from sera_ig.cli import run_command_line

    @contextmanager
    def fake_connect(account=None, **kwargs):
        yield fake_client

    monkeypatch.setattr(client_module, "connect", fake_connect)

    code = run_command_line(["inbox", "-o", "json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data[0]["title"]


def test_run_command_line_reports_usage_errors(capsys) -> None:
    from sera_ig.cli import run_command_line

    code = run_command_line(["definitely-not-a-command"])
    assert code != 0
    captured = capsys.readouterr()
    assert "No such command" in captured.err
    assert "seraig" in captured.err


def test_run_command_line_returns_zero_for_help(capsys) -> None:
    from sera_ig.cli import run_command_line

    assert run_command_line(["--help"]) == 0
    assert "Usage" in capsys.readouterr().out
