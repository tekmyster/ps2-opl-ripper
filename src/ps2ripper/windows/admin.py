from __future__ import annotations

from .native import is_elevated


def require_administrator() -> None:
    if not is_elevated():
        raise PermissionError(
            "PS2 OPL Ripper requires Administrator access for raw disk and optical-drive operations."
        )
