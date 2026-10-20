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

- **A real app in your terminal.** Five screens, a working mouse, and twenty-one
  themes — not a list of subcommands.
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

### On Windows

Windows is fully supported — the app, the mouse and the themes all work there.
A normal install is enough:

```powershell
pipx install git+https://github.com/serhabdel/sera-ig-cli.git
```

If the install stops with `Failed to install: sera_ig_cli-*.whl`, the real
reason is printed just above that line — read it, or re-run with
`pipx install --verbose …`.

**The most common Windows failure** is this one, and it is not a problem with
this package:

```
Caused by: Failed to update Windows PE resources: C:\Users\…\Temp\.tmpXXXX\uv-trampoline-1234.exe
Caused by: The system cannot open the device or file specified. (os error -2147024786)
```

pipx installs with [`uv`](https://github.com/astral-sh/uv) when it is
available, and on Windows `uv` patches a small launcher `.exe` in `%TEMP%`.
Antivirus and EDR products (Windows Defender, Bitdefender, Avast …) lock that
file mid-write and the install dies. It is a known upstream issue:
[astral-sh/uv#20792](https://github.com/astral-sh/uv/issues/20792).

Use pip instead of uv — that skips the launcher entirely:

```powershell
pipx uninstall sera-ig-cli
pipx install --backend pip git+https://github.com/serhabdel/sera-ig-cli.git
```

If the environment is already registered with the uv backend, `pipx` keeps
using it — so either uninstall first as above, or rebuild it explicitly:

```powershell
pipx reinstall --backend pip sera-ig-cli
```

Other ways around it:

```powershell
# update uv — 0.9.9+ stores the launcher metadata differently
uv self update

# or point TEMP at a folder your antivirus does not scan
$env:TEMP = "$env:USERPROFILE\tmp"; $env:TMP = $env:TEMP
New-Item -ItemType Directory -Force $env:TEMP
```

Plain pip always works, and prints the error in full:

```powershell
py -m pip install --user --upgrade pip
py -m pip install --user git+https://github.com/serhabdel/sera-ig-cli.git
```

The one-turn commands work on Windows without any of this.

Older consoles (the classic `conhost` rather than Windows Terminal) may not
report mouse clicks. The app stays fully usable from the keyboard there.

## Quick start

```bash
seraig                      # the app — a graphical interface in your terminal
seraig auth login           # sign in (asks for username, password, 2FA code)
seraig inbox                # your conversations
seraig read noor            # read a conversation
seraig send noor --text "hi there"
seraig shell                # the classic command prompt
```

### The app

Running `seraig` with no arguments opens a graphical interface in the
terminal — five screens, a mouse, and themes:

```
┌─ Chats ───────────────────────────────────────────────────────────────────┐
│ ⭘  seraig — Instagram in your terminal                                     │
│  Chats   Feed   Stories   Notifications   Settings                        │
├──────────────────────┬───────────────────────────────────────────────────┤
│  Filter conversations │  noor                                              │
│ ┌────────────────────┐│                                                   │
│ │  N   noor           ││  ▏ 2026-05-01 11:58                               │
│ │      hey there      ││    hey there                                      │
│ │  S   Weekend plans  ││                                                   │
│ │      works for me  ││  ▏ 2026-05-01 11:58                               │
│ └────────────────────┘│    La ana                                          │
├──────────────────────┴───────────────────────────────────────────────────┤
│ ❯ write a message…                                    [ Send ]              │
└────────────────────────────────────────────────────────────────────────────┘
```

**Everything works with the mouse**: click a conversation to open it, click a
message to select it, scroll to move through the conversation, click a button
to act. Every mouse action has a keyboard equivalent, so the app is fully
usable from the keyboard alone.

| Key | Action |
| --- | --- |
| `Ctrl+P` | Command palette — runs the CLI commands and the app actions |
| `Ctrl+T` | Cycle to the next theme |
| `Ctrl+R` | Reload what is on screen |
| `Ctrl+F` | Focus the conversation filter |
| `Ctrl+Enter` | Send the message you are writing |
| `Ctrl+Q` | Quit |
| `Tab` | Move between panes |
| `↑` `↓` / `j` `k` | Move through a list |
| `Esc` | Close the overlay, or drop the selection |
| Click | Open a conversation, or select a message |
| Double click | Copy a message |
| Scroll | Scroll the list or the conversation |

The interface is drawn immediately and keeps a spinner going while Instagram
answers, so it never shows a blank screen — even on a slow connection.

Every action costs as few round trips as possible: listing the inbox is one
request, opening a conversation is one request (it brings the messages with
it), and sending a message is one request. Set
`advanced.request_delay` to `0` to drop the one-second pause instagrapi takes
before each request.

### The classic prompt

`seraig shell` opens a prompt where every command is available without
repeating the program name:

```
seraig(@noor) ❯ inbox
seraig(@noor) ❯ read noor
seraig(@noor) ❯ send noor --text "hi there"
```

- `Tab` completes command names, subcommands and their options.
- `↑`/`↓` walk the history; `Ctrl-R` searches it.
- `-o json` works exactly as it does on the command line.
- `help`, `clear` and `exit` are built in.
- `tui chat` opens the full-screen interface from inside the shell.

The shell is also available on its own with `seraig shell`.

### Two-factor authentication

If your account has 2FA, the CLI handles it three ways — pick whichever fits:

```bash
# 1. interactive — it prompts for the code when Instagram asks for one
seraig auth login --account youruser

# 2. supply the code yourself (TOTP, an SMS/email code, or a backup code)
seraig auth login --account youruser --password-stdin --code 123456

# 3. fully unattended — store the TOTP seed once, then the code is
#    generated locally and the login never asks for anything
seraig config set login.totp_secret GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ
echo 'your-password' | seraig auth login --account youruser --password-stdin
```

The TOTP seed is the base32 secret Instagram shows when you set up an
authenticator app. It is read from `--totp-secret`, the `SERA_IG_TOTP_SECRET`
environment variable, or `login.totp_secret` in the config — in that order.
The config file is mode `0600`, and secret values are redacted by
`seraig config get` / `list`.

> The seed is a second factor. Anyone with it can generate valid codes for
> your account. Keep it as private as your password.

You only need this once: the session is stored and reused, so later commands
never ask for a code again.

## Commands

### Authentication

| Command | What it does |
| --- | --- |
| `seraig auth login` | Sign in and store the session |
| `seraig auth logout` | Sign out and delete the local session |
| `seraig auth switch <user>` | Make another saved account the default |
| `seraig auth whoami` | Show the account in use |
| `seraig auth accounts` | List every account with a saved session |

`auth login` takes `--account/-a`, `--password-stdin`, `--code` and
`--totp-secret` — see [Two-factor authentication](#two-factor-authentication).

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

### The app screens

```bash
seraig                    # the app, on the Chats screen
seraig app                # the same thing, said explicitly
seraig app --screen feed  # open straight on the feed
seraig tui chat           # the Chats screen
seraig tui feed           # the Feed screen
seraig tui stories        # the Stories screen
seraig tui notify         # the Notifications screen
```

| Screen | What it shows |
| --- | --- |
| **Chats** | The conversation list, the open conversation, and a composer |
| **Feed** | The posts of the people you follow |
| **Stories** | The stories of the people you follow |
| **Notifications** | Likes, comments, follows and mentions |
| **Settings** | Themes, the image protocol, the toggles and the key map |

### Themes

Twenty-one themes ship with the app — `nord`, `gruvbox`, `tokyo-night`,
`solarized-light`, `atom-one-dark`, `catppuccin-mocha`, `dracula`, `flexoki`,
`rose-pine` and more. `Ctrl+T` cycles through them, the Settings screen picks
one, and the choice is remembered.

```bash
seraig theme list          # every theme, and which one is active
seraig theme set nord      # use it from now on
seraig theme show nord     # the colours it resolves to
```

Your own themes go in `~/.sera-ig-cli/themes/<name>.json`:

```json
{
  "primary": "#88C0D0",
  "secondary": "#81A1C1",
  "accent": "#B48EAD",
  "background": "#2E3440",
  "variables": { "panel": "#3B4252" }
}
```

### Images

Every conversation and post shows a coloured avatar with the person's
initial. The colour comes from a hash of the username, so it is the same on
every machine and never waits on the network.

Set `ui.avatar_images` to `true` to fetch the real profile pictures — they are
cached in `~/.sera-ig-cli/cache/avatars/`.

Media attached to a message is drawn in the terminal. The protocol is
detected automatically:

```bash
seraig config set ui.image_protocol halfblock
```

`auto` (the default) picks `kitty` in Kitty and WezTerm, `iterm2` in iTerm2,
and `halfblock` everywhere else. You can also force `ascii`, `braille`,
`kitty`, `iterm2`, `sixel`, or turn images off with `none`.

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
├── history                  # shell command history
├── logs/                    # debug logs
└── downloads/               # default download target
```

Set `SERA_IG_HOME` to move the whole thing somewhere else.

| Setting | Default | What it does |
| --- | --- | --- |
| `login.current_username` | – | The account to use |
| `login.totp_secret` | – | Authenticator seed, so 2FA needs no input |
| `chat.page_size` | 20 | Messages fetched per thread |
| `output.format` | `text` | `text` or `json` |
| `advanced.request_delay` | 1 | Seconds to wait before each request (instagrapi's anti-detection pause — **0 is fastest**) |
| `advanced.debug` | `false` | Write debug logs to `logs/` |

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
├── commands/     # one module per command group — the agent API
├── app/          # the Textual application
│   ├── main.py   # the root app: tabs, theme, palette
│   ├── chat.py   # conversations, messages, the composer
│   ├── feed.py   stories.py  notify.py  settings.py
│   ├── widgets.py  palette.py  themes.py  images.py  worker.py
├── shell.py      # the classic prompt
└── config.py     # the YAML settings store
```

The application is built on
[Textual](https://github.com/Textualize/textual), which gives it real mouse
support on Linux, macOS **and** Windows, twenty-one themes, a command
palette, and a headless test driver that can simulate clicks in CI.

Every call to Instagram is blocking, and the interface is driven by an event
loop, so every call runs on a worker thread and the result is handed back to
the interface. That is what keeps the app responsive on a slow connection.

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

pytest              # 185 tests, no network access needed
ruff check .
```

The test suite runs entirely against a fake client that returns real instagrapi
model objects, so nothing touches the network. The application is tested
headlessly, driving it with synthetic key presses and **mouse clicks** through
Textual's `Pilot`, and a few screens are checked against SVG snapshots.

## Credits

- [`instagrapi`](https://github.com/subzeroid/instagrapi) — the private API client that does the heavy lifting.
- [`instagram-cli`](https://github.com/supreme-gg-gg/instagram-cli) — the terminal-Instagram idea this project is built on.
- [`typer`](https://github.com/fastapi/typer) · [`rich`](https://github.com/Textualize/rich) — the CLI and its output.

## License

MIT © 2026 Seradyx Lab — see [LICENSE](LICENSE).

Made by [Seradyx Lab](https://seradyx.tech).
