"""Running the blocking Instagram calls without freezing the interface.

Textual's event loop is single threaded, and every call to Instagram is a
blocking socket read. So every call runs on a worker thread, and the result
is handed back to the interface with :meth:`App.call_from_thread`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from textual.widget import Widget

logger = logging.getLogger(__name__)

#: The worker group used for Instagram calls. Workers in the same group with
#: ``exclusive=True`` cancel each other, so a fast re-navigation cannot
#: deliver a stale result.
INSTAGRAM_GROUP = "instagram"


def describe_error(exc: BaseException) -> str:
    """Turn an exception into the short message the interface shows."""
    from ..errors import translate

    return str(translate(exc))


def run(
    app: Any,
    work: Callable[[], Any],
    on_success: Callable[[Any], None],
    on_error: Callable[[BaseException], None],
    *,
    group: str = INSTAGRAM_GROUP,
    exclusive: bool = True,
) -> Any:
    """Run *work* on a worker thread and deliver the outcome to the interface.

    ``work`` must be a plain blocking callable — it is never called on the
    event-loop thread.
    """

    def runner() -> None:
        try:
            result = work()
        except BaseException as exc:  # noqa: BLE001 - reported to the user
            logger.debug("Background call failed", exc_info=True)
            app.call_from_thread(on_error, exc)
        else:
            app.call_from_thread(on_success, result)

    return app.run_worker(
        runner,
        group=group,
        exclusive=exclusive,
        thread=True,
        exit_on_error=False,
    )


class PanelBase(Widget):
    """Mixin for the panels: every blocking call goes through :func:`run`."""

    def fetch(
        self,
        work: Callable[[], Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[BaseException], None] | None = None,
        *,
        group: str = INSTAGRAM_GROUP,
        exclusive: bool = True,
    ) -> Any:
        """Run *work* on a worker thread and hand the outcome back."""
        return run(
            self.app,
            work,
            on_success,
            on_error if on_error is not None else self.fail,
            group=group,
            exclusive=exclusive,
        )

    def fail(self, exc: BaseException) -> None:
        """Report a failed call without taking the application down."""
        self.app.report_error(exc)
