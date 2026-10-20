# AI Coding Assistant Context

Context for AI coding tools (Claude Code, Cursor, Codex, Gemini CLI, …) working
on this repository.

## Project overview

- `sera-ig-cli` is an **Instagram terminal client written in Python**, built on
  the private mobile API via [`instagrapi`](https://github.com/subzeroid/instagrapi).
- There are **two surfaces**, and both matter:
  - **one-turn commands** (`seraig inbox`, `seraig send …`) — for humans, scripts
    and agents. This is a **frozen public contract**; the JSON shapes are
    stable and must not change.
  - **the application** (`seraig`, `seraig app`) — a [Textual](https://github.com/Textualize/textual)
    app with tabs, a mouse, and themes. This is where new UI work happens.
- The CLI framework is **typer**; the output is **rich**; the app is **Textual**.
- The console script is `seraig`.

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
├── commands/     # one module per command group — the agent API
├── app/          # the Textual application
│   ├── main.py   # the root app: tabs, theme, palette
│   ├── chat.py   # conversations, messages, the composer
│   ├── feed.py   # stories.py    notify.py   settings.py
│   ├── widgets.py  # avatars, rows, bubbles, record panels
│   ├── search.py   # the message search overlay
│   ├── menu.py     # the action menu and the prompt
│   ├── palette.py  # the command palette provider
│   ├── themes.py   # built-in themes + user theme files
│   ├── images.py   # protocol detection, avatars, thumbnails
│   └── worker.py   # running the blocking calls off the event loop
├── shell.py      # the classic prompt_toolkit prompt
└── click_compat.py  # click, standalone or vendored inside typer
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
  `SeraError` subclasses; the CLI turns those into an exit code. The handler
  table resolves exception names **dynamically** — instagrapi renames them
  between releases and a missing class must never break the translator.
- **Keep `connect()` as the only way to reach a logged-in client.** It handles
  session restore and saving refreshed cookies. It does **not** validate the
  session up front: that costs a round trip before every command, and an
  expired session already surfaces as `LoginRequired`.
- **Never block the event loop.** Every call to Instagram is blocking and the
  app is driven by asyncio, so every call must run inside `app/worker.py`'s
  `run()` — which uses `@work(thread=True)` and hands the result back with
  `call_from_thread`. A call on the loop thread freezes the interface.
- **`request_timeout` in instagrapi is a pause between requests, not an HTTP
  timeout.** It is bound to `advanced.request_delay` (1 second). A session
  restored from disk carries its own value, so the delay is re-applied after
  `set_settings()`.
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
- The app is tested **headlessly** with `App.run_test()` and Textual's
  `Pilot`, which can press keys and **click widgets**:
  ```python
  async with app.run_test() as pilot:
      await pilot.click("#conversation-item-0")
  ```
- A few screens are checked against SVG snapshots in `tests/snapshots/`.
  Delete a file to record a new one.
- New commands need: a text renderer, a JSON payload, and a CLI test.
- New app behaviour needs: a headless app test.

## Gotchas worth knowing

- A widget's stylesheet lives in `DEFAULT_CSS`, **not** `CSS` — `CSS` is
  ignored on widgets, and only `App` uses it.
- `Widget.refresh()` is a Textual built-in; do not shadow it. Use `reload()`.
- `App.current_theme` is the `Theme` object, not its name — use `App.theme`
  to set it, and `theme_name` to read the name back.
- Textual CSS takes integer margins, not percentages. To right-align a
  widget, set `align-horizontal: right` on it.
- A `Static` inside a `ListItem` must not stop the click event, or the
  `ListView` never selects it.
- **Removing and mounting widgets are deferred.** Always `await` them, and
  make the callback a coroutine — `App.call_from_thread` awaits a coroutine
  for you. Skipping the wait leaves two widgets with the same id and the
  application crashes with `DuplicateIds`.
- A widget's classes must be set when it is constructed, in the `classes`
  argument. Setting them afterwards does not reach the stylesheet.

## Security considerations

- Credentials only ever come from the terminal prompt, `--password-stdin`, or
  the `SERA_IG_PASSWORD` environment variable. Never store them in the config
  file, and never echo them.
- The account's session file is the only long-lived secret. Keep it `0600` and
  out of version control.
- Debug logs go to `~/.sera-ig-cli/logs/`. Ask the user for them when
  troubleshooting, and remind them to redact usernames.
