from __future__ import annotations

import logging
import traceback
from collections.abc import Callable

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(object, str)
    progress = Signal(object)
    finished = Signal()


class TaskWorker(QRunnable):
    def __init__(self, function: Callable[..., object], *args: object, **kwargs: object) -> None:
        super().__init__()
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.function(*self.args, progress=self.signals.progress.emit, **self.kwargs)
        except BaseException as exc:
            details = traceback.format_exc()
            logger.error("Background task failed\n%s", details)
            self.signals.error.emit(exc, details)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
