# AI Coding Assistant Context

Context for AI coding tools (Claude Code, Cursor, Codex, Gemini CLI, …) working
on this repository.

## Project overview

- `sera-ig-cli` is an **Instagram terminal client written in Python**, built on
  the private mobile API via [`instagrapi`](https://github.com/subzeroid/instagrapi).
- The CLI framework is **typer**; the output is **rich**; the TUI is **curses**
  (no third-party TUI library).
- The console script is `seraig`.
- Two surfaces exist and both matter:
  - **one-turn commands** (`seraig inbox`, `seraig send …`) — for humans, scripts and agents;
  - **the TUI** (`seraig tui chat`) — keyboard-driven, for humans.

## Layout

```
sera_ig/
├── api.py        # every call to Instagram; returns plain dicts
├── client.py     # session storage, login, 2FA / challenge handling
├── models.py     # instagrapi objects → flat JSON dicts
├── resolve.py    # "noor" / "weekend plans" → a DM thread
├── output.py     # text and JSON rendering helpers
├── config.py     # the YAML settings store
├── errors.py     # instagrapi exceptions → user-facing messages
├── state.py      # the account and output format for the current run
├── commands/     # one module per command group
└── tui/          # the curses interfaces
```

## Build, test and lint

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                 # the whole suite, no network needed
ruff check .
seraig --help          # smoke test the CLI
```

## Conventions

- **Never call Instagram outside `api.py`.** Commands parse arguments and
  format output; `api.py` owns the protocol. This keeps the surface swappable
  and the tests offline.
- **Return plain dicts, not pydantic models.** Every dict becomes JSON, and the
  JSON schema is a public contract for agents. Add a field only if it is
  genuinely useful; do not rename existing ones.
- **`-o json` must stay machine-readable.** No escape codes, no tables, no
  progress output on stdout in JSON mode. Human output goes through
  `output.py`.
- **Wrap every instagrapi call** so a failure becomes a short message instead
  of a traceback. `errors.translate()` maps the library's exceptions onto
  `SeraError` subclasses; the CLI turns those into an exit code.
- **Keep `connect()` as the only way to reach a logged-in client.** It handles
  session restore, validation and saving refreshed cookies.
- **Sessions are secrets.** They live in `~/.sera-ig-cli/users/<username>/`
  with mode `0600`. Never commit them, never log them.
- **Do not add bot behaviour.** This is a client for a human's own account:
  no bulk messaging, no auto-DMs, no scraping loops. New features should help
  a person read and reply, not act without them.

## Testing

- The suite runs against `tests/fakes.py`, a fake client that returns **real
  instagrapi model objects** (`DirectThread`, `DirectMessage`, `Media`, …), so
  the normalisation code is exercised against production types.
- Patch `sera_ig.client.connect` to inject the fake into the commands:
  ```python
  monkeypatch.setattr(client_module, "connect", fake_connect)
  ```
- The curses layer is hard to test. Keep the logic it depends on pure and
  testable (see `tests/test_tui.py`), and verify the real interface in a pty.
- New commands need: a text renderer, a JSON payload, and a CLI test.

## Security considerations

- Credentials only ever come from the terminal prompt, `--password-stdin`, or
  the `SERA_IG_PASSWORD` environment variable. Never store them in the config
  file, and never echo them.
- The account's session file is the only long-lived secret. Keep it `0600` and
  out of version control.
- Debug logs go to `~/.sera-ig-cli/logs/`. Ask the user for them when
  troubleshooting, and remind them to redact usernames.
