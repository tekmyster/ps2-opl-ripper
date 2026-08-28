from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from threading import Event, Lock

from .exceptions import CancelledError


class CancellationToken:
    """Thread-safe cooperative cancellation with protected critical sections."""

    def __init__(self) -> None:
        self._requested = Event()
        self._lock = Lock()
        self._critical_depth = 0

    @property
    def is_requested(self) -> bool:
        return self._requested.is_set()

    @property
    def in_critical_section(self) -> bool:
        with self._lock:
            return self._critical_depth > 0

    def request(self) -> None:
        self._requested.set()

    def checkpoint(self) -> None:
        if self.is_requested and not self.in_critical_section:
            raise CancelledError("Operation cancelled.")

    @contextmanager
    def critical_section(self, checkpoint_on_exit: bool = True) -> Iterator[None]:
        with self._lock:
            self._critical_depth += 1
        try:
            yield
        finally:
            with self._lock:
                self._critical_depth -= 1
            if checkpoint_on_exit:
                self.checkpoint()
