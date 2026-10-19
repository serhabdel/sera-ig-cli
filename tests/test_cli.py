"""End-to-end CLI tests using a fake Instagram client."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from typer.testing import CliRunner

from sera_ig import cli
from sera_ig import client as client_module

from .fakes import FakeClient

runner = CliRunner()


@pytest.fixture
def connected(monkeypatch, fake_client) -> Iterator[FakeClient]:
    """Make every command talk to the fake client."""

    @contextmanager
    def fake_connect(account=None, **kwargs):
        yield fake_client

    monkeypatch.setattr(client_module, "connect", fake_connect)
    yield fake_client


def run(*args: str):
    """Invoke the CLI and return the result."""
    return runner.invoke(cli.app, list(args))


# ------------------------------------------------------------------ generic
def test_banner_is_shown_without_a_command() -> None:
    result = run()
    assert result.exit_code == 0
    assert "seraig" in result.stdout.lower() or "brainrot" in result.stdout.lower()


def test_version_flag() -> None:
    result = run("--version")
    assert result.exit_code == 0
    assert "sera-ig-cli" in result.stdout


def test_help_lists_the_main_commands() -> None:
    result = run("--help")
    assert result.exit_code == 0
    for command in ("inbox", "send", "feed", "stories", "auth", "tui"):
        assert command in result.stdout


def test_unknown_output_format_is_rejected() -> None:
    result = run("-o", "yaml", "inbox")
    assert result.exit_code != 0


# --------------------------------------------------------------------- auth
def test_auth_whoami_without_account() -> None:
    result = run("auth", "whoami")
    assert result.exit_code == 0
    assert "No account" in result.stdout


def test_auth_accounts_is_empty_on_a_fresh_install() -> None:
    result = run("auth", "accounts")
    assert result.exit_code == 0
    assert "No accounts" in result.stdout


def test_auth_switch_requires_a_session() -> None:
    result = run("auth", "switch", "ghost")
    assert result.exit_code != 0


# -------------------------------------------------------------------- inbox
def test_inbox_text_output(connected) -> None:
    result = run("inbox")
    assert result.exit_code == 0
    assert "Weekend plans" in result.stdout


def test_inbox_json_output(connected) -> None:
    result = run("-o", "json", "inbox")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert isinstance(data, list)
    assert data[0]["title"]


def test_inbox_json_output_per_command(connected) -> None:
    result = run("inbox", "-o", "json")
    assert result.exit_code == 0
    assert json.loads(result.stdout)


def test_inbox_search(connected) -> None:
    result = run("-o", "json", "inbox", "--search", "sara")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert len(data) == 1


# --------------------------------------------------------------------- read
def test_read_resolves_a_thread_by_username(connected) -> None:
    result = run("-o", "json", "read", "abdel")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["messages"][0]["text"] == "hey there"


def test_read_reports_an_unknown_thread(connected) -> None:
    result = run("read", "nobody-here-at-all")
    assert result.exit_code != 0


# --------------------------------------------------------------------- send
def test_send_delivers_the_message(connected) -> None:
    result = run("send", "abdel", "--text", "hello from the cli")
    assert result.exit_code == 0
    assert connected.sent[-1]["text"] == "hello from the cli"


def test_send_without_text_or_media_fails(connected) -> None:
    result = run("send", "abdel")
    assert result.exit_code != 0


def test_reply_passes_the_referenced_message(connected) -> None:
    result = run("reply", "Weekend plans", "--message-id", "9002", "--text", "sure")
    assert result.exit_code == 0
    assert connected.sent[-1]["reply_to"] == "9002"


def test_react_sends_the_emoji(connected) -> None:
    result = run("react", "abdel", "--message-id", "9001", "--emoji", "🔥")
    assert result.exit_code == 0
    assert connected.reactions[-1]["emoji"] == "🔥"


def test_unsend_deletes_the_message(connected) -> None:
    result = run("unsend", "abdel", "--message-id", "9001")
    assert result.exit_code == 0
    assert connected.unsent[-1]["message_id"] == 9001


def test_seen_marks_the_thread(connected) -> None:
    result = run("seen", "abdel")
    assert result.exit_code == 0
    assert connected.seen_threads


# --------------------------------------------------------------------- feed
def test_feed_json(connected) -> None:
    result = run("-o", "json", "feed")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data[0]["code"] == "ABC123"


def test_reels_json(connected) -> None:
    result = run("-o", "json", "reels")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["kind"] == "reel"


def test_stories_json(connected) -> None:
    result = run("-o", "json", "stories")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["user"]["username"] == "abdel"


def test_stories_for_one_user(connected) -> None:
    result = run("-o", "json", "stories", "abdel")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["kind"] == "photo"


def test_notify_json(connected) -> None:
    result = run("-o", "json", "notify")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["type"] == "like"


# --------------------------------------------------------------------- user
def test_user_profile(connected) -> None:
    result = run("-o", "json", "user", "abdel")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["followers"] == 345


def test_posts(connected) -> None:
    result = run("-o", "json", "posts", "abdel")
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 1


def test_followers(connected) -> None:
    result = run("-o", "json", "followers", "abdel")
    assert result.exit_code == 0
    assert json.loads(result.stdout)[0]["username"] == "fan1"


# -------------------------------------------------------------------- media
def test_post_details(connected) -> None:
    result = run("-o", "json", "post", "ABC123")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["code"] == "ABC123"


def test_like(connected) -> None:
    result = run("-o", "json", "like", "ABC123")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["liked"] is True


def test_comment(connected) -> None:
    result = run("-o", "json", "comment", "ABC123", "--text", "nice")
    assert result.exit_code == 0
    assert json.loads(result.stdout)["text"] == "nice"


def test_download(connected, tmp_path) -> None:
    target = tmp_path / "out.jpg"
    result = run("-o", "json", "download", "ABC123", "-d", str(target))
    assert result.exit_code == 0
    assert json.loads(result.stdout)["path"] == str(target)


# ------------------------------------------------------------------- config
def test_config_set_and_get(connected) -> None:
    assert run("config", "set", "chat.page_size", "42").exit_code == 0
    result = run("config", "get", "chat.page_size")
    assert result.exit_code == 0
    assert "42" in result.stdout


def test_config_list_as_json(connected) -> None:
    result = run("-o", "json", "config", "list")
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert any(item["key"] == "chat.page_size" for item in data)


def test_doctor_runs(connected) -> None:
    result = run("doctor")
    assert result.exit_code == 0
    assert "instagrapi" in result.stdout
