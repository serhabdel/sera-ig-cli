"""The Chats panel — the heart of the application."""

from __future__ import annotations

from typing import Any

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Label, ListItem, ListView, Static, TextArea

from .. import api
from ..output import format_time, relative_time
from .images import render_image, supports_images
from .widgets import Avatar, Clickable
from .worker import PanelBase

CONVERSATION_LIMIT = 20
MESSAGE_LIMIT = 50


class ConversationRow(Clickable):
    """One conversation in the list."""

    def __init__(
        self,
        record: dict[str, Any],
        *,
        show_avatar: bool = True,
        client: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.record = record
        self.show_avatar = show_avatar
        self.client = client

    def compose(self) -> ComposeResult:
        user = (self.record.get("users") or [{}])[0]
        username = user.get("username") or self.record.get("title") or "?"
        last = self.record.get("last_message") or {}
        preview = (last.get("text") or f"[{last.get('kind', 'message')}]").replace("\n", " ")
        when = relative_time(self.record.get("last_activity_at"))

        with Horizontal(classes="conversation-row"):
            yield Avatar(
                username,
                enabled=self.show_avatar,
                client=self.client,
                user=user,
                classes="row-avatar",
            )
            with Vertical(classes="conversation-text"):
                yield Label(Text(self.record.get("title") or username), classes="row-title")
                yield Label(Text(preview[:60]), classes="row-preview")
            yield Label(Text(when), classes="row-time")

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
    .media-placeholder {
        color: $text-muted;
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
        if not url:
            self.show_placeholder()
            return
        if not supports_images(self.protocol):
            self.show_placeholder()
            return

        def work() -> Any:
            response = self.client.private.get(url, timeout=30)
            response.raise_for_status()
            return response.content

        self.run_worker(self._draw, work)

    def _draw(self, work: Any) -> None:
        """Run the download on a worker thread, then draw the result."""
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


class MessageBubble(Clickable):
    """One message in the conversation."""

    def __init__(
        self,
        record: dict[str, Any],
        *,
        client: Any = None,
        protocol: str = "halfblock",
        selected: bool = False,
        **kwargs: Any,
    ) -> None:
        self.client = client
        self.protocol = protocol
        mine = bool(record.get("is_sent_by_viewer"))
        classes = str(kwargs.pop("classes", "") or "")
        classes = f"{classes} message-bubble {'own' if mine else 'theirs'}"
        if selected:
            classes += " selected"
        super().__init__(classes=classes, **kwargs)
        self.record = record
        self.selected = selected

    def compose(self) -> ComposeResult:
        record = self.record
        stamp = format_time(record.get("timestamp"))
        body = record.get("text") or ""
        media = record.get("media")

        with Vertical(classes="bubble"):
            yield Label(Text(stamp, style="dim"), classes="message-time")
            yield Label(Text(body), classes="message-text")
            if media and (media.get("url") or media.get("pk")):
                yield MediaPreview(self.client, media, self.protocol, classes="message-media")
            elif media:
                yield Label(Text(f"[{media.get('type', 'media')}]"), classes="message-media")

    def on_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.Pressed(self))

    def on_double_click(self, event: Any) -> None:
        event.stop()
        self.post_message(self.DoublePressed(self))


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
    #conversation-list {
        height: 1fr;
        background: $surface;
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
        text-style: bold;
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
    }
    .message-bubble {
        height: auto;
        width: 100%;
        margin: 0 0 1 0;
    }
    .message-bubble > .bubble {
        width: 70%;
        height: auto;
        padding: 0 1;
        border-left: solid $secondary;
    }
    .message-bubble.own {
        align-horizontal: right;
    }
    .message-bubble.own > .bubble {
        border-left: none;
        border-right: solid $accent;
    }
    .message-bubble.selected > .bubble {
        background: $panel;
    }
    .message-time {
        color: $text-muted;
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
    #send {
        width: 12;
        min-width: 12;
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
        Binding("ctrl+r", "refresh_list", "Refresh"),
    ]

    def __init__(self, client: Any, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.client = client
        self.conversations: list[dict[str, Any]] = []
        self.messages: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.current_thread: Any = None
        self.loaded = False
        self.typing = False
        self._cache: dict[str, list[dict[str, Any]]] = {}
        self.selected_message: str | None = None
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
                yield Button("Unsend", id="act-unsend")
                yield Button("Copy", id="act-copy")
            with Horizontal(id="composer"):
                yield TextArea(id="composer-input")
                yield Button("Send", id="send", variant="primary")

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

    def _apply_conversations(self, records: list[dict[str, Any]]) -> None:
        self.conversations = records or []
        self.loaded = True
        listing = self.query_one("#conversation-list", ListView)
        listing.clear()
        show_avatar = self.app.show_avatars
        for index, record in enumerate(self.conversations):
            row = ConversationRow(
                record,
                show_avatar=show_avatar,
                client=self.client,
                id=f"conversation-{index}",
            )
            listing.append(ListItem(row, id=f"conversation-item-{index}"))
        if not self.conversations:
            self.set_status("No conversations")
        else:
            self.set_status(f"{len(self.conversations)} conversations")
            self._prefetch_first()

    def _prefetch_first(self) -> None:
        """Warm the first conversation, so the first click is instant.

        It is off by default: it costs a request that is wasted when the
        first conversation is never opened.
        """
        if self._cache or not self.conversations:
            return
        if not self.app.prefetch:
            return
        thread_id = self.conversations[0]["id"]

        def work() -> Any:
            return api.read_conversation(self.client, thread_id, limit=MESSAGE_LIMIT)

        def keep(result: Any) -> None:
            self._cache[thread_id] = result[1]

        self.fetch(work, keep, group="prefetch", exclusive=False)

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
        cached = self._cache.get(record["id"])
        if cached is not None:
            self._apply_thread((self.current_thread, cached))

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

    def _apply_thread(self, result: tuple[Any, list[dict[str, Any]]]) -> None:
        self.current_thread, records = result
        if self.current is not None:
            self._cache[self.current["id"]] = records
        self._apply_messages(records)

    def _apply_messages(self, records: list[dict[str, Any]]) -> None:
        self.messages = records or []
        container = self.query_one("#message-list", VerticalScroll)
        container.remove_children()
        for record in self.messages:
            bubble = MessageBubble(
                record,
                client=self.client,
                protocol=self.app.image_protocol,
                selected=record["id"] == self.selected_message,
                id=f"message-{record['id']}",
            )
            container.mount(bubble)
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
        self._append_bubble(optimistic)

        def work() -> Any:
            return api.send_text(self.client, self._thread_for(self.current), text)

        self.fetch(work, self._confirm_sent, self._failed_to_send)

    def _confirm_sent(self, record: dict[str, Any]) -> None:
        self._remove_bubble(f"pending-{len(self.messages)}")
        self.messages.append(record)
        self._append_bubble(record)

    def _failed_to_send(self, exc: BaseException) -> None:
        from .worker import describe_error

        self.set_status(f"Could not send: {describe_error(exc)}", error=True)
        self.app.report_error(exc)

    def _append_bubble(self, record: dict[str, Any]) -> None:
        container = self.query_one("#message-list", VerticalScroll)
        bubble = MessageBubble(
            record,
            client=self.client,
            protocol=self.app.image_protocol,
            id=f"message-{record['id']}",
        )
        container.mount(bubble)
        container.scroll_end(animate=False)

    def _remove_bubble(self, bubble_id: str) -> None:
        for bubble in self.query(f"#message-{bubble_id}"):
            bubble.remove()

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

    def fail(self, exc: BaseException) -> None:
        """Report a failed call: the status line and a toast."""
        from .worker import describe_error

        self.set_status(describe_error(exc), error=True)
        self.app.report_error(exc)

    def set_status(self, text: str, *, error: bool = False) -> None:
        """Show a line of status under the conversation list."""
        status = self.query_one("#chat-status", Static)
        status.update(Text(text))
        status.set_class(error, "error")

    def reload(self) -> None:
        """Reload the conversation list."""
        self.load_conversations(self.query_one("#chat-filter", Input).value.strip())

    def action_refresh_list(self) -> None:
        self.reload()

    def action_focus_filter(self) -> None:
        self.query_one("#chat-filter", Input).focus()

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

    def _unsend_selected(self) -> None:
        record = self._selected_record()
        if record is None or self.current is None:
            return
        self.fetch(
            lambda: api.unsend(self.client, self._thread_for(self.current), record["id"]),
            lambda _: self._remove_bubble(record["id"]),
        )

    def on_text_area_changed(self, event: Any) -> None:
        """Notice when the user is writing, so a refresh stays out of the way."""
        if getattr(event, "text_area", None) is not None and event.text_area.id == "composer-input":
            self.typing = bool(event.text_area.text.strip())

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the conversation list as the user types."""
        if event.input.id != "chat-filter":
            return
        if self._filter_timer is not None:
            self._filter_timer.stop()
        value = event.value.strip()
        self._filter_timer = self.set_timer(0.3, lambda: self.load_conversations(value))
