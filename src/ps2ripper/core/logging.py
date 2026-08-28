from __future__ import annotations

import hashlib
import logging
import os
import platform
from logging.handlers import RotatingFileHandler
from pathlib import Path

from ps2ripper import __version__


def default_log_directory() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / "PS2OPLRipper" / "Logs"


def configure_logging(log_directory: Path | None = None, verbose: bool = False) -> Path:
    directory = log_directory or default_log_directory()
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "PS2OPLRipper.log"
    handler = RotatingFileHandler(
        log_path, maxBytes=4 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    logging.getLogger(__name__).info(
        "PS2 OPL Ripper %s started on %s %s",
        __version__,
        platform.system(),
        platform.version(),
    )
    return log_path


def serial_for_log(serial: str) -> str:
    """Keep logs useful for identity changes without storing the full serial."""
    if not serial:
        return "unavailable"
    return "sha256:" + hashlib.sha256(serial.encode("utf-8", "replace")).hexdigest()[:16]
