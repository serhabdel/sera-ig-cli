# sera-ig-cli

**Instagram in your terminal.** A private-API Instagram client built on
[`instagrapi`](https://github.com/subzeroid/instagrapi) — chat, feed, stories
and notifications without opening a browser.

A [Seradyx Lab](https://seradyx.tech) project.

> [!WARNING]
> This project is not affiliated with, authorized by, or endorsed by Instagram
> or Meta. It is an independent, unofficial project. Using the private API may
> violate Meta's Terms of Service, and automated access can get an account
> restricted. Use it at your own risk, and never with an account you cannot
> afford to lose.

```
 ____                      ___   ____
/ ___|   ___  _ __   __ _ |_ _| / ___|
\___ \  / _ \| '__| / _` | | | | |  _
 ___) ||  __/| |   | (_| | | | | |_| |
|____/  \___||_|    \__,_||___| \____|

The end of brainrot and doomscrolling is here.
```

## Why?

- **Keyboard only.** No mouse, no touchscreen, no infinite scroll.
- **Scriptable.** Every command takes `-o json` for machine-readable output.
- **Agent-friendly.** A flat, stable JSON schema on every single command.
- **One login, forever.** The session is stored locally and reused; you
  authenticate once per account.

## Install

Requires Python 3.10 or newer.

```bash
pipx install git+https://github.com/serhabdel/sera-ig-cli.git
```

or with pip:

```bash
pip install git+https://github.com/serhabdel/sera-ig-cli.git
```

From a clone:

```bash
git clone https://github.com/serhabdel/sera-ig-cli.git
cd sera-ig-cli
pip install -e .
```

Video uploads need a few extra system libraries:

```bash
pip install "sera-ig-cli[video]"
```

## Quick start

```bash
seraig auth login          # sign in (asks for username, password, 2FA code)
seraig inbox              # your conversations
seraig read noor         # read a conversation
seraig send noor --text "hi there"
seraig tui chat           # the full keyboard-driven interface
```

## Commands

### Authentication

| Command | What it does |
| --- | --- |
| `seraig auth login` | Sign in and store the session |
| `seraig auth logout` | Sign out and delete the local session |
| `seraig auth switch <user>` | Make another saved account the default |
| `seraig auth whoami` | Show the account in use |
| `seraig auth accounts` | List every account with a saved session |

### Direct messages

| Command | What it does |
| --- | --- |
| `seraig inbox` | List conversations (`--filter unread`, `--search name`) |
| `seraig read <thread>` | Read the messages of a conversation |
| `seraig send <thread> --text "…"` | Send a message |
| `seraig send <thread> --media photo.jpg` | Send a photo or video |
| `seraig reply <thread> --message-id <id> --text "…"` | Reply to one message |
| `seraig react <thread> --message-id <id> --emoji 🔥` | React with an emoji |
| `seraig unsend <thread> --message-id <id>` | Delete a message you sent |
| `seraig seen <thread>` | Mark a conversation as read |
| `seraig download-message <thread> --message-id <id>` | Save an attachment |
| `seraig search <name>` | Find people on Instagram |

`<thread>` accepts a **thread id**, a **username** (`noor` or `@noor`), or a
fuzzy **conversation title** (`weekend plans`).

### Browsing

| Command | What it does |
| --- | --- |
| `seraig feed` | Posts from the people you follow |
| `seraig reels` | Reels (`--explore` for the explore tab) |
| `seraig stories [user]` | Stories of the people you follow, or of one account |
| `seraig notify` | Likes, comments, follows and mentions |
| `seraig user <name>` | Profile summary |
| `seraig posts <name>` | The latest posts of an account |
| `seraig followers <name>` / `seraig following <name>` | Social graph |

### Media

| Command | What it does |
| --- | --- |
| `seraig post <media>` | Details of a post |
| `seraig like <media>` | Like a post (`--unlike` to undo) |
| `seraig comment <media> --text "…"` | Comment on a post |
| `seraig comments <media>` | List the comments |
| `seraig download <media> [-d path]` | Save a photo or video |

`<media>` accepts a numeric id, a short code (`ABC123`) or a full URL.

### The TUI

```bash
seraig tui chat          # conversations + messages, keyboard driven
seraig tui chat noor    # jump straight into a conversation
seraig tui feed          # scroll the home timeline
```

| Key | Action |
| --- | --- |
| `Tab` | Switch between the conversation list and the input |
| `↑` `↓` (or `j` / `k`) | Move through the list / scroll messages |
| `Enter` | Open a conversation, or send what you typed |
| `/` | Search conversations |
| `:r` | Refresh |
| `:q` | Quit |
| `Ctrl-C` | Quit |

### Configuration

```bash
seraig config list                 # every setting
seraig config get chat.page_size
seraig config set chat.page_size 50
seraig config edit                 # open in $EDITOR
```

Everything lives in `~/.sera-ig-cli/`:

```
~/.sera-ig-cli/
├── config.yaml              # your settings
├── users/<username>/
│   └── session.json         # the instagrapi session (mode 0600)
├── logs/                    # debug logs
└── downloads/               # default download target
```

Set `SERA_IG_HOME` to move the whole thing somewhere else.

## JSON output — built for agents

Every command supports `-o json`. The output is flat, stable and free of
terminal escape codes.

```bash
seraig inbox -o json
seraig read noor -o json --limit 5
seraig send noor --text "ping" -o json
```

```json
[
  {
    "id": "340282366841510300949128268610842297468",
    "title": "noor",
    "users": [{ "pk": "123", "username": "noor", "is_private": false }],
    "last_activity_at": "2026-05-01T11:57:00+00:00",
    "last_message": {
      "id": "9001",
      "kind": "text",
      "text": "hey there",
      "is_sent_by_viewer": false
    }
  }
]
```

Global flags work too — `seraig -o json inbox` and `seraig inbox -o json` are
equivalent. `--account <username>` picks a different saved account for a
single run.

## How it works

`sera-ig-cli` talks to the **private mobile API** through
[`instagrapi`](https://github.com/subzeroid/instagrapi) — the same API the
official iOS and Android apps use. There is no official Instagram API for
consumer messaging, so this is how a terminal client gets a real, full-featured
inbox.

```
sera_ig/
├── api.py        # every call to Instagram, returning plain dicts
├── client.py     # session storage, login, 2FA and challenge handling
├── models.py     # instagrapi objects → flat JSON
├── resolve.py    # "noor" / "weekend plans" → a thread
├── commands/     # one module per command group
├── tui/          # the curses interfaces
└── config.py     # the YAML settings store
```

Sessions are stored per account and reused. After a successful login the
cookies and device identifiers are written to
`~/.sera-ig-cli/users/<username>/session.json` with mode `0600`, and refreshed
on every command so a login only has to happen once.

## Development

```bash
git clone https://github.com/serhabdel/sera-ig-cli.git
cd sera-ig-cli
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest              # 101 tests, no network access needed
ruff check .
```

The test suite runs entirely against a fake client that returns real instagrapi
model objects, so nothing touches the network.

## Credits

- [`instagrapi`](https://github.com/subzeroid/instagrapi) — the private API client that does the heavy lifting.
- [`instagram-cli`](https://github.com/supreme-gg-gg/instagram-cli) — the terminal-Instagram idea this project is built on.
- [`typer`](https://github.com/fastapi/typer) · [`rich`](https://github.com/Textualize/rich) — the CLI and its output.

## License

MIT © 2026 Seradyx Lab — see [LICENSE](LICENSE).

Made by [Seradyx Lab](https://seradyx.tech).
