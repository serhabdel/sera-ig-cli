---
name: sera-ig-skill
description: >
  How to use the sera-ig-cli Instagram terminal client to read and send Instagram
  direct messages, check the inbox, browse the feed, stories and notifications on
  behalf of a user. Use this skill whenever the user wants to send or read
  Instagram messages, check their DMs, reply to or unsend a message, react to a
  message, or automate an Instagram DM workflow from the command line. It also
  covers tasks phrased as "message X on Instagram", "check my Instagram inbox",
  "send a photo to my friend", "read my unread Instagram threads", or any
  automation involving Instagram direct messages.
---

# sera-ig-cli — Agent Usage Guide

`seraig` is a terminal client for Instagram that talks to the private mobile
API. For agents it exposes **one-turn commands** that print to stdout and exit
— ideal for scripting and tool use.

> Every one-turn command needs the user to be logged in (`seraig auth login`).
> If a command returns an auth error, ask the user to log in themselves — do
> not try to log in on their behalf, and never ask for their password.
>
> If the account has two-factor authentication, the user handles that too: the
> CLI prompts for the code, accepts `--code`, or generates it from a stored
> TOTP seed. Never ask the user for a 2FA code, an SMS code, a backup code,
> or the TOTP seed — ask them to run `seraig auth login` themselves.

---

## Thread resolution

Every command that targets a conversation takes a `<thread>` argument, resolved
in this order:

1. **Thread id** — a long number like `340282366841510300949128268610842297468`
2. **Username** — an exact Instagram username (`noor` or `@noor`)
3. **Conversation title** — fuzzy match on the group title (`"weekend plans"`)

**Best practice for multi-step work:** run `seraig inbox -o json` first, take
the `id` from the conversation you want, and pass that id to every later
command. It skips the search entirely and is far more reliable than matching
on names.

---

## JSON output

Every command accepts `-o json` (also `--output json`). Use it whenever you
parse the result.

The payload is **flat and unwrapped** — the command's data *is* the JSON, with
no envelope:

```json
{ "id": "9001", "kind": "text", "text": "hey there", "is_sent_by_viewer": false }
```

Text output is for humans; JSON output never contains escape codes or tables.

---

## Commands

### List the inbox

```bash
seraig inbox -o json
seraig inbox -o json --filter unread
seraig inbox -o json --search sara
```

Returns a list of conversations:

```json
[
  {
    "id": "340282366841510300949128268610842297468",
    "title": "noor",
    "usernames": ["noor"],
    "is_group": false,
    "last_activity_at": "2026-05-01T11:57:00+00:00",
    "last_message": { "id": "9001", "kind": "text", "text": "hey there" }
  }
]
```

### Read a conversation

```bash
seraig read noor -o json --limit 20
seraig read 340282366841510300949128268610842297468 -o json --mark-seen
```

Messages come back **oldest first**, which is how a conversation reads.

```json
{
  "thread": { "id": "…", "title": "noor", "usernames": ["noor"] },
  "messages": [
    { "id": "9001", "kind": "text", "text": "hey there", "timestamp": "…" }
  ]
}
```

### Send a message

```bash
seraig send noor --text "see you at 8"
seraig send noor --media ./photo.jpg
seraig send noor --media ./clip.mp4 --text "watch this"
```

`kind` tells you what was actually sent: `text`, `media`, `media_share`,
`reel`, `story_share`, `link` or `visual_media`.

### Reply, react, unsend, mark as read

```bash
seraig reply noor --message-id 9001 --text "sure, see you there"
seraig react noor --message-id 9001 --emoji "🔥"
seraig unsend noor --message-id 9001
seraig seen noor
```

Message ids come from `read` — the `id` field of each message.

### Save an attachment

```bash
seraig download-message noor --message-id 9001 -d ./photo.jpg
```

### Find people

```bash
seraig search sara -o json
```

### Browse

```bash
seraig feed -o json --limit 10
seraig reels -o json
seraig stories -o json            # the people you follow
seraig stories noor -o json      # one account
seraig notify -o json
seraig user noor -o json
seraig posts noor -o json
```

### Posts

```bash
seraig post ABC123 -o json
seraig like ABC123 -o json
seraig comment ABC123 --text "nice shot" -o json
seraig download ABC123 -d ./post.jpg
```

A `<media>` reference is a numeric id, a short code (`ABC123`) or a full URL.

---

## Multiple accounts

```bash
seraig auth accounts            # what is saved
seraig auth switch sara         # change the default
seraig inbox --account sara     # use one account for a single run
```

## The interactive surfaces

`seraig` with no arguments opens a graphical application, and `seraig shell`
opens a prompt where commands are typed without the program name (`inbox`,
`read noor`, …). Both are the same command surface as the command line, with
the same `-o json` output.

**Do not use either from an agent.** They need a terminal, they wait for
input, and they never terminate on their own. Use the one-turn commands.

---

## Recommended workflow

1. `seraig inbox -o json` → find the conversation, note its `id`.
2. `seraig read <id> -o json --limit 30` → read the recent messages.
3. Reply with context:
   `seraig reply <id> --message-id <message-id> --text "…"`.

Read before you write. Replying to the right message matters more than
replying fast.

---

## Errors

| Exit code | Meaning | What to do |
| --- | --- | --- |
| 2 | Not logged in / session expired | Ask the user to run `seraig auth login` |
| 3 | Thread, user or media not found | Check the id with `seraig inbox -o json` |
| 4 | The command cannot work as asked | Fix the arguments |
| 5 | Rate limited | Wait, then retry |
Error messages are printed on stderr in a single line. A missing conversation
suggests close matches — offer those to the user rather than guessing.

---

## What not to do

- Do not log in, or ask for a password, a 2FA code or a verification code.
- Do not send messages the user did not ask for, and do not send several
  messages when one will do.
- Do not build loops, bulk messaging or scraping on top of these commands —
  that is bot behaviour, it breaks accounts, and it is out of scope for this
  project.
- Do not use the application (`seraig` with no arguments) or the prompt
  (`seraig shell`) — they need a terminal and never terminate on their own.
  Use the one-turn commands.
