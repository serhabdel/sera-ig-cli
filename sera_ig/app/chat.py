"""The Chats panel — the heart of the application."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import MouseDown
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, TextArea

from .. import api
from ..output import format_time, relative_time
from .images import render_image, supports_images
from .widgets import Avatar, Clickable
from .worker import PanelBase

CONVERSATION_LIMIT = 20
MESSAGE_LIMIT = 50
#: Two messages from the same person within this many seconds are one group.
GROUP_WINDOW = 300


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO timestamp into a datetime."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def group_flags(records: list[dict[str, Any]]) -> list[bool]:
    """Say which messages start a new group.

    Consecutive messages from the same person, close together in time, are
    shown as one block — the way a chat app groups them.
    """
    flags: list[bool] = []
    previous: dict[str, Any] | None = None
    previous_time: datetime | None = None

    for record in records:
        current_time = _parse_time(record.get("timestamp"))
        same_person = (
            previous is not None
            and previous.get("is_sent_by_viewer") == record.get("is_sent_by_viewer")
            and previous.get("user_id") == record.get("user_id")
        )
        close_in_time = (
            current_time is not None
            and previous_time is not None
            and abs((current_time - previous_time).total_seconds()) <= GROUP_WINDOW
        )
        flags.append(not (same_person and close_in_time))
        previous = record
        previous_time = current_time
    return flags


class ConversationRow(Clickable):
    """One conversation in the list."""

    def __init__(
        self,
        record: dict[str, Any],
        *,
        show_avatar: bool = True,
        client: Any = None,
        active: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.record = record
        self.show_avatar = show_avatar
        self.client = client
        self.active = active

    def compose(self) -> ComposeResult:
        user = (self.record.get("users") or [{}])[0]
        username = user.get("username") or self.record.get("title") or "?"
        last = self.record.get("last_message") or {}
        preview = (last.get("text") or f"[{last.get('kind', 'message')}]").replace("\n", " ")
        when = relative_time(self.record.get("last_activity_at"))
        unread = bool(last.get("text")) and self.record.get("unread", False)

        with Horizontal(classes="conversation-row"):
            yield Avatar(
                username,
                enabled=self.show_avatar,
                client=self.client,
                user=user,
                classes="row-avatar",
            )
            with Vertical(classes="conversation-text"):
                title = Text(self.record.get("title") or username)
                if unread:
                    title.stylize("bold")
                if self.active:
                    title.append(" ●", style="green")
                yield Label(title, classes="row-title")
                yield Label(Text(preview[:60]), classes="row-preview")
            yield Label(Text(when), classes="row-time")

    def on_double_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.DoublePressed(self))


class MessageBubble(Clickable):
    """One message in the conversation."""

    def __init__(
        self,
        record: dict[str, Any],
        *,
        client: Any = None,
        protocol: str = "halfblock",
        selected: bool = False,
        grouped: bool = True,
        seen: bool = False,
        **kwargs: Any,
    ) -> None:
        self.client = client
        self.protocol = protocol
        self.grouped = grouped
        self.seen = seen
        mine = bool(record.get("is_sent_by_viewer"))
        classes = str(kwargs.pop("classes", "") or "")
        classes = f"{classes} message-bubble {'own' if mine else 'theirs'}"
        if not grouped:
            classes += " grouped"
        super().__init__(classes=classes, **kwargs)
        self.record = record
        self.selected = selected

    def compose(self) -> ComposeResult:
        record = self.record
        stamp = format_time(record.get("timestamp"))
        body = record.get("text") or ""
        media = record.get("media")

        with Vertical(classes="bubble"):
            reply = record.get("reply_to")
            if reply and reply.get("text"):
                yield Label(
                    Text(f"↳ {reply['text'][:60]}", style="italic dim"),
                    classes="message-reply",
                )
            if self.grouped and stamp:
                yield Label(Text(stamp, style="dim"), classes="message-time")
            if body:
                yield Label(Text(body), classes="message-text")
            if media and (media.get("url") or media.get("pk")):
                yield MediaPreview(self.client, media, self.protocol, classes="message-media")
            elif media:
                yield Label(Text(f"[{media.get('type', 'media')}]"), classes="message-media")

            reactions = record.get("reactions") or []
            if reactions:
                emojis = "".join(r["emoji"] for r in reactions)
                yield Label(Text(f"{emojis} {record.get('likes_count', 0)}"), classes="message-reactions")
            elif record.get("likes_count"):
                yield Label(Text(f"♥ {record['likes_count']}"), classes="message-reactions")

            if self.seen:
                yield Label(Text("Seen", style="dim"), classes="message-seen")

    def on_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.Pressed(self))

    def on_double_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.DoublePressed(self))


class MediaPreview(Static):
    """The media attached to a message.

    The picture is downloaded in the background and drawn with whichever
    protocol the terminal supports. When the terminal cannot draw images, or
    the download fails, a readable placeholder is shown instead.
    """

    DEFAULT_CSS = """
    MediaPreview {
        height: auto;
        width: 100%;
    }
    """

    def __init__(self, client: Any, media: dict[str, Any], protocol: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.media = media
        self.protocol = protocol

    def on_mount(self) -> None:
        self.load_media()

    def load_media(self) -> None:
        """Fetch and draw the picture."""
        url = self.media.get("url")
        if not url or not supports_images(self.protocol):
            self.show_placeholder()
            return

        def work() -> Any:
            response = self.client.private.get(url, timeout=30)
            response.raise_for_status()
            return response.content

        from .worker import run

        run(
            self.app,
            work,
            self._apply,
            self._failed,
            group="media",
            exclusive=False,
        )

    def _apply(self, data: bytes) -> None:
        rendered = render_image(data, 40, self.protocol, height=12)
        if rendered is None:
            self.show_placeholder()
            return
        self.update(rendered)

    def _failed(self, exc: BaseException) -> None:
        self.show_placeholder()

    def show_placeholder(self) -> None:
        """Show a readable stand-in for the picture."""
        kind = self.media.get("type") or "media"
        if self.media.get("pk"):
            self.update(Text(f"[{kind} · post {self.media['pk']}]", style="dim"))
        else:
            self.update(Text(f"[{kind}]", style="dim"))


class ChatPanel(PanelBase):
    """Conversations on the left, the open conversation on the right."""

    DEFAULT_CSS = """
    ChatPanel {
        layout: horizontal;
    }
    #conversation-pane {
        width: 34;
        border-right: solid $panel;
    }
    #chat-filter {
        margin: 0 0 1 0;
    }
    #chat-filter:focus {
        border: tall $accent;
    }
    #conversation-list {
        height: 1fr;
        background: $surface;
        scrollbar-size-vertical: 1;
    }
    #conversation-list > ListItem {
        background: $surface;
        padding: 0 1;
        height: 3;
    }
    #conversation-list > ListItem.--highlight {
        background: $panel;
    }
    ConversationRow {
        height: 100%;
    }
    .conversation-row {
        height: 100%;
    }
    .row-avatar {
        width: 5;
        height: 100%;
        content-align: left top;
    }
    .conversation-text {
        width: 1fr;
    }
    .row-title {
        text-style: none;
    }
    .row-preview, .row-time {
        color: $text-muted;
    }
    .row-time {
        width: 10;
        text-align: right;
    }
    #message-pane {
        width: 1fr;
    }
    #chat-title {
        height: 1;
        padding: 0 1;
        background: $panel;
        text-style: bold;
    }
    #message-list {
        height: 1fr;
        padding: 1 2;
        scrollbar-size-vertical: 1;
    }
    .message-bubble {
        height: auto;
        width: 100%;
        margin: 0 0 1 0;
    }
    .message-bubble.grouped {
        margin: 0 0 0 0;
    }
    .message-bubble > .bubble {
        width: 66%;
        height: auto;
        padding: 0 1;
        border-top: round $secondary;
        border-bottom: round $secondary;
        border-left: round $secondary;
    }
    .message-bubble.own {
        align-horizontal: right;
    }
    .message-bubble.own > .bubble {
        border-left: none;
        border-right: round $accent;
    }
    .message-bubble.selected > .bubble {
        background: $panel;
    }
    .message-time, .message-reply, .message-seen {
        color: $text-muted;
    }
    .message-reactions {
        color: $accent;
    }
    #action-bar {
        height: auto;
        display: none;
    }
    #action-bar.visible {
        display: block;
    }
    #composer {
        height: 5;
    }
    #composer-input {
        width: 1fr;
    }
    #composer-input:focus {
        border: tall $accent;
    }
    #send {
        width: 12;
        min-width: 12;
    }
    #send:disabled {
        opacity: 50%;
    }
    #chat-status {
        height: 1;
        color: $text-muted;
        padding: 0 1;
    }
    #chat-status.error {
        color: $error;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "send_message", "Send", priority=True),
        Binding("ctrl+f", "focus_filter", "Filter"),
        Binding("ctrl+s", "search_messages", "Search"),
        Binding("ctrl+r", "refresh_list", "Refresh"),
    ]

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.conversations: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.current_thread: Any = None
        self.selected_message: str | None = None
        self.loaded = False
        self.typing = False
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self._pending_bubble: MessageBubble | None = None
        self._seen: set[str] = set()
        self._presence: dict[str, bool] = {}
        self._requests = 0
        self._filter_timer: Any = None

    # ------------------------------------------------------------- layout
    def compose(self) -> ComposeResult:
        with Vertical(id="conversation-pane"):
            yield Input(placeholder="Filter conversations", id="chat-filter")
            yield ListView(id="conversation-list")
            yield Static("", id="chat-status")
        with Vertical(id="message-pane"):
            yield Static("No conversation open", id="chat-title")
            yield VerticalScroll(id="message-list")
            with Horizontal(id="action-bar"):
                yield Button("Reply", id="act-reply", variant="primary")
                yield Button("React", id="act-react")
                yield Button("Like", id="act-like")
                yield Button("Unsend", id="act-unsend")
                yield Button("Copy", id="act-copy")
            with Horizontal(id="composer"):
                yield TextArea(id="composer-input")
                yield Button("Send", id="send", variant="primary", disabled=True)

    def on_mount(self) -> None:
        self.load_conversations()

    # -------------------------------------------------------------- data
    def load_conversations(self, search: str = "") -> None:
        """Fetch the conversation list in the background."""
        self.set_status("Loading conversations…" if not search else f"Searching {search}…")
        self.fetch(
            lambda: api.list_threads(
                self.client,
                amount=CONVERSATION_LIMIT,
                search=search or None,
                message_limit=1,
            ),
            self._apply_conversations,
        )

    async def _apply_conversations(self, records: list[dict[str, Any]]) -> None:
        """Show the conversations.

        Removing and mounting are both deferred in Textual, so they have to
        be awaited: otherwise a second render can land on top of the first
        one and the widget ids collide.
        """
        self.conversations = records or []
        self.loaded = True
        listing = self.query_one("#conversation-list", ListView)
        await listing.clear()
        show_avatar = self.app.show_avatars
        for index, record in enumerate(self.conversations):
            row = ConversationRow(
                record,
                show_avatar=show_avatar,
                client=self.client,
                active=self._presence.get(
                    str((record.get("users") or [{}])[0].get("pk") or ""), False
                ),
                id=f"conversation-{index}",
            )
            await listing.append(ListItem(row, id=f"conversation-item-{index}"))
        if not self.conversations:
            self.set_status("No conversations yet — press ^S to search your messages")
        else:
            self.set_status(f"{len(self.conversations)} conversations")
        self._load_presence()

    def _load_presence(self) -> None:
        """Find out who is active right now."""
        user_ids = [
            str(user.get("pk"))
            for record in self.conversations
            for user in (record.get("users") or [])
            if user.get("pk")
        ]
        if not user_ids:
            return

        def work() -> Any:
            return api.users_presence(self.client, user_ids)

        def apply(active: dict[str, bool]) -> None:
            self._presence = active or {}
            for record in self.conversations:
                pk = str((record.get("users") or [{}])[0].get("pk") or "")
                record["active"] = self._presence.get(pk, False)
            self.app.call_later(self._refresh_rows)

        self.fetch(work, apply, group="presence", exclusive=False)

    async def _refresh_rows(self) -> None:
        """Redraw the conversation list after the presence arrives."""
        listing = self.query_one("#conversation-list", ListView)
        for index, record in enumerate(self.conversations):
            pk = str((record.get("users") or [{}])[0].get("pk") or "")
            row = listing.query_one(f"#conversation-{index}", ConversationRow)
            row.active = self._presence.get(pk, False)

    def open_conversation(self, index: int) -> None:
        """Open the conversation at *index*."""
        if not (0 <= index < len(self.conversations)):
            return
        record = self.conversations[index]
        self.current = record
        self.current_thread = None
        self.query_one("#chat-title", Static).update(
            Text(record.get("title") or (record.get("usernames") or [""])[0])
        )
        self.query_one("#message-list", VerticalScroll).remove_children()
        self.set_status("Loading messages…")
        self.fetch(
            lambda: api.read_conversation(
                self.client, record["id"], limit=MESSAGE_LIMIT
            ),
            self._apply_thread,
        )

    def _thread_for(self, record: dict[str, Any]) -> Any:
        """Return the open thread, without asking Instagram for it again."""
        if self.current_thread is not None:
            return self.current_thread
        return api.get_thread(self.client, record["id"])

    async def _apply_thread(self, result: tuple[Any, list[dict[str, Any]]]) -> None:
        self.current_thread, records = result
        if self.current is not None:
            self._cache[self.current["id"]] = records
        await self._apply_messages(records)
        self._mark_seen(records)
        # The conversation is open, so the composer is ready for a reply.
        self.query_one("#composer-input", TextArea).focus()

    def _mark_seen(self, records: list[dict[str, Any]]) -> None:
        """Tell Instagram the newest message has been read."""
        if not records or self.current is None:
            return
        newest = records[-1]
        message_id = newest.get("id")
        if not message_id or message_id in self._seen:
            return
        self._seen.add(str(message_id))

        def work() -> Any:
            return api.mark_message_seen(self.client, self.current["id"], message_id)

        self.fetch(work, lambda _: None, group="seen", exclusive=False)

    async def _apply_messages(self, records: list[dict[str, Any]]) -> None:
        """Show the messages of the open conversation.

        The removal and the mounting are awaited, so a refresh can never
        leave two bubbles with the same id in the list.
        """
        self.messages = records or []
        container = self.query_one("#message-list", VerticalScroll)
        await container.remove_children()
        flags = group_flags(self.messages)
        bubbles = []
        seen: set[str] = set()
        for record, grouped in zip(self.messages, flags, strict=True):
            key = str(record.get("id"))
            if key in seen:
                # Instagram can repeat a message; showing it twice would
                # also collide on the widget id.
                continue
            seen.add(key)
            bubbles.append(
                MessageBubble(
                    record,
                    client=self.client,
                    protocol=self.app.image_protocol,
                    selected=record["id"] == self.selected_message,
                    grouped=grouped,
                    seen=key in self._seen,
                    id=f"message-{key}",
                )
            )
        await container.mount_all(bubbles)
        container.scroll_end(animate=False)
        self.set_status("")

    # ------------------------------------------------------------ actions
    def action_send_message(self) -> None:
        """Send what is in the composer."""
        composer = self.query_one("#composer-input", TextArea)
        text = composer.text.strip()
        if not text:
            return
        composer.text = ""
        self.send(text)

    def send(self, text: str) -> None:
        """Send *text*, showing it straight away."""
        if self.current is None:
            self.set_status("Open a conversation first", error=True)
            return

        optimistic = {
            "id": f"pending-{len(self.messages)}",
            "text": text,
            "timestamp": None,
            "is_sent_by_viewer": True,
            "media": None,
            "pending": True,
        }

        async def show() -> None:
            self._pending_bubble = await self._append_bubble(optimistic)

        # Show it straight away, then let the server have its say.
        self.app.call_next(show)

        def work() -> Any:
            return api.send_text(self.client, self._thread_for(self.current), text)

        self.fetch(work, self._confirm_sent, self._failed_to_send)

    async def _confirm_sent(self, record: dict[str, Any]) -> None:
        """Swap the optimistic bubble for the one the server confirmed."""
        pending = self._pending_bubble
        self._pending_bubble = None
        if pending is not None:
            await pending.remove()
        else:
            await self._remove_bubble(f"pending-{len(self.messages)}")
        self.messages.append(record)
        await self._append_bubble(record)

    def _failed_to_send(self, exc: BaseException) -> None:
        from .worker import describe_error

        self.set_status(f"Could not send: {describe_error(exc)}", error=True)
        self.app.report_error(exc)

    async def _append_bubble(self, record: dict[str, Any]) -> MessageBubble:
        """Add one bubble to the conversation and return it."""
        container = self.query_one("#message-list", VerticalScroll)
        bubble = MessageBubble(
            record,
            client=self.client,
            protocol=self.app.image_protocol,
            id=f"message-{record['id']}",
        )
        await container.mount(bubble)
        container.scroll_end(animate=False)
        return bubble

    async def _remove_bubble(self, bubble_id: str) -> None:
        """Take a bubble out of the conversation, waiting for it to go."""
        for bubble in self.query(f"#message-{bubble_id}"):
            await bubble.remove()

    def select_message(self, message_id: str) -> None:
        """Mark a message as selected and show the action bar."""
        self.selected_message = message_id
        for bubble in self.query(MessageBubble):
            bubble.selected = bubble.record.get("id") == message_id
            bubble.set_class(bubble.selected, "selected")
        self.query_one("#action-bar").set_class(True, "visible")

    def clear_selection(self) -> None:
        """Drop the selected message."""
        self.selected_message = None
        for bubble in self.query(MessageBubble):
            bubble.selected = False
            bubble.set_class(False, "selected")
        self.query_one("#action-bar").set_class(False, "visible")

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show a line of status under the conversation list."""
        status = self.query_one("#chat-status", Static)
        status.update(Text(text))
        status.set_class(error, "error")

    def fail(self, exc: BaseException) -> None:
        """Report a failed call: the status line and a toast."""
        from .worker import describe_error

        self.set_status(describe_error(exc), error=True)
        self.app.report_error(exc)

    def reload(self) -> None:
        """Reload the conversation list."""
        self.load_conversations(self.query_one("#chat-filter", Input).value.strip())

    def action_refresh_list(self) -> None:
        self.reload()

    def action_focus_filter(self) -> None:
        self.query_one("#chat-filter", Input).focus()

    def action_search_messages(self) -> None:
        """Search every message you have ever received."""
        self.app.search_messages()

    # -------------------------------------------------------------- events
    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        for index in range(len(self.conversations)):
            if item.id == f"conversation-item-{index}":
                self.open_conversation(index)
                return

    def on_clickable_pressed(self, event: Clickable.Pressed) -> None:
        widget = event.widget
        if isinstance(widget, MessageBubble):
            self.select_message(widget.record.get("id", ""))

    def on_clickable_double_pressed(self, event: Clickable.DoublePressed) -> None:
        widget = event.widget
        if isinstance(widget, MessageBubble):
            self.app.copy_to_clipboard(widget.record.get("text", ""))
            self.app.notify("Copied", title="Message")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button = event.button.id
        if button == "send":
            self.action_send_message()
        elif button == "act-reply":
            self._reply_to_selected()
        elif button == "act-react":
            self._react_to_selected()
        elif button == "act-like":
            self._like_selected()
        elif button == "act-unsend":
            self._unsend_selected()
        elif button == "act-copy":
            record = self._selected_record()
            if record:
                self.app.copy_to_clipboard(record.get("text", ""))
                self.app.notify("Copied", title="Message")

    def _selected_record(self) -> dict[str, Any] | None:
        if self.selected_message is None:
            return None
        for record in self.messages:
            if record.get("id") == self.selected_message:
                return record
        return None

    def _reply_to_selected(self) -> None:
        record = self._selected_record()
        if record is None:
            return
        composer = self.query_one("#composer-input", TextArea)
        composer.focus()
        composer.text = f"@{(self.current or {}).get('title', '')} "

    def _react_to_selected(self) -> None:
        record = self._selected_record()
        if record is None or self.current is None:
            return
        self.fetch(
            lambda: api.react(self.client, self._thread_for(self.current), record["id"], "❤"),
            lambda _: self.app.notify("Reacted ❤", title="Message"),
        )

    def _like_selected(self) -> None:
        record = self._selected_record()
        if record is None or self.current is None:
            return
        self.fetch(
            lambda: api.like_message(self.client, self.current["id"], record["id"]),
            lambda _: self.app.notify("Liked ❤", title="Message"),
        )

    def _unsend_selected(self) -> None:
        record = self._selected_record()
        if record is None or self.current is None:
            return
        self.fetch(
            lambda: api.unsend(self.client, self._thread_for(self.current), record["id"]),
            lambda _: self._remove_bubble(record["id"]),
        )

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the conversation list as the user types."""
        if event.input.id != "chat-filter":
            return
        if self._filter_timer is not None:
            self._filter_timer.stop()
        value = event.value.strip()
        self._filter_timer = self.set_timer(0.3, lambda: self.load_conversations(value))

    def on_text_area_changed(self, event: Any) -> None:
        """Notice when the user is writing, so a refresh stays out of the way."""
        area = getattr(event, "text_area", None)
        if area is None or area.id != "composer-input":
            return
        self.typing = bool(area.text.strip())
        self.query_one("#send", Button).disabled = not self.typing

    def on_mouse_down(self, event: MouseDown) -> None:
        """A right click opens the actions for what is under the pointer."""
        if event.button != 2:
            return
        event.stop()
        target = event.widget
        if isinstance(target, MessageBubble):
            self.app.show_message_menu(self, target.record)
        elif isinstance(target, ConversationRow):
            self.app.show_conversation_menu(self, target.record)

    # ------------------------------------------------------- menu actions
    def run_message_action(self, key: str, record: dict[str, Any]) -> None:
        """Do what the message menu was asked to do."""
        if key == "reply":
            self.selected_message = record.get("id")
            self._reply_to_selected()
        elif key == "react":
            self.selected_message = record.get("id")
            self._react_to_selected()
        elif key == "like":
            self.selected_message = record.get("id")
            self._like_selected()
        elif key == "copy":
            self.app.copy_to_clipboard(record.get("text", ""))
            self.app.notify("Copied", title="Message")
        elif key == "unsend":
            self.selected_message = record.get("id")
            self._unsend_selected()

    def run_conversation_action(self, key: str, record: dict[str, Any]) -> None:
        """Do what the conversation menu was asked to do."""
        thread_id = record.get("id")
        if not thread_id:
            return
        if key == "open":
            self.open_thread_by_id(thread_id)
        elif key == "mute":
            self.fetch(
                lambda: api.mute_thread(self.client, thread_id),
                lambda _: self.app.notify("Muted", title="Conversation"),
            )
        elif key == "unread":
            self.fetch(
                lambda: api.mark_thread_unread(self.client, thread_id),
                lambda _: self.app.notify("Marked as unread", title="Conversation"),
            )
        elif key == "rename":
            self.app.rename_conversation(self, record)

    def open_thread_by_id(self, thread_id: str) -> None:
        """Open a conversation by its id, even if it is not in the list."""
        for index, record in enumerate(self.conversations):
            if str(record.get("id")) == str(thread_id):
                self.open_conversation(index)
                return
        # Not in the inbox — fetch it on its own.
        self.set_status("Opening conversation…")
        self.fetch(
            lambda: api.read_conversation(self.client, thread_id, limit=MESSAGE_LIMIT),
            self._apply_thread,
        )
