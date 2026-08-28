from __future__ import annotations

import ctypes
import logging
import os
import sys
from ctypes import wintypes

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QMessageBox

from ps2ripper import __version__
from ps2ripper.core.logging import configure_logging
from ps2ripper.windows.native import is_elevated


def _relaunch_elevated() -> bool:
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteW.argtypes = [
        wintypes.HWND,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        ctypes.c_int,
    ]
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    if getattr(sys, "frozen", False):
        executable = sys.executable
        parameters = "--elevated"
    else:
        executable = sys.executable
        parameters = "-m ps2ripper.app --elevated"
    result = shell32.ShellExecuteW(None, "runas", executable, parameters, os.getcwd(), 1)
    return int(result or 0) > 32


def main() -> int:
    QCoreApplication.setOrganizationName("PS2OPLRipper")
    QCoreApplication.setApplicationName("PS2OPLRipper")
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationDisplayName("PS2 OPL Ripper")
    log_path = configure_logging()
    if not is_elevated():
        if "--elevated" not in sys.argv and _relaunch_elevated():
            return 0
        QMessageBox.critical(
            None,
            "Administrator access required",
            "PS2 OPL Ripper requires Administrator access for raw disk and optical-drive operations. "
            "No privilege bypass is available.",
        )
        return 1
    from ps2ripper.ui.main_window import MainWindow

    logging.getLogger(__name__).info("Starting GUI version %s", __version__)
    window = MainWindow(log_path)
    if "--self-test" in sys.argv:
        # Packaging smoke path: construct every eagerly imported UI/native layer
        # without showing dialogs, mutating storage, or starting the event loop.
        window.deleteLater()
        return 0
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
