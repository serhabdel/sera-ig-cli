"""Running slow work off the UI thread.

Instagram's API can take seconds to answer, and sometimes much longer. A TUI
that calls it inline shows a blank screen while it waits, so every network
call runs in a worker thread and the interface keeps drawing.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any


class Task:
    """A single background job with a result, an error and a done flag."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.result: Any = None
        self.error: BaseException | None = None
        self.done = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        try:
            self.result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:  # noqa: BLE001 - reported to the UI
            self.error = exc
        finally:
            self.done = True

    def start(self) -> Task:
        """Start the job."""
        self._thread.start()
        return self

    @property
    def running(self) -> bool:
        """Whether the job is still in flight."""
        return not self.done


class Background:
    """Runs one job at a time and hands the result back to the UI."""

    def __init__(self) -> None:
        self._task: Task | None = None

    @property
    def busy(self) -> bool:
        """Whether a job is in flight."""
        return self._task is not None and self._task.running

    def start(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Begin a job, replacing any job that is still running."""
        self._task = Task(fn, *args, **kwargs).start()

    def take(self) -> tuple[Any, BaseException | None] | None:
        """Return the finished result, or ``None`` while still running."""
        if self._task is None or not self._task.done:
            return None
        result, error = self._task.result, self._task.error
        self._task = None
        return result, error
