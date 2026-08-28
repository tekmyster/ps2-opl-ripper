from __future__ import annotations

import re

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.ps2.system_cnf import normalize_game_id

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
OPL_ISO_FILENAME_LIMIT = 160


def sanitize_title(title: str) -> str:
    value = _ILLEGAL.sub(" ", title)
    value = _WHITESPACE.sub(" ", value).strip(" .")
    if not value:
        raise ValidationError("Enter a game title containing at least one valid character.")
    if value.upper() in _RESERVED:
        value += " Game"
    return value


def opl_iso_filename(game_id: str, title: str, limit: int = OPL_ISO_FILENAME_LIMIT) -> str:
    normalized_id = normalize_game_id(game_id)
    safe_title = sanitize_title(title)
    suffix = ".iso"
    fixed = f"{normalized_id}."
    remaining = limit - len(fixed) - len(suffix)
    if remaining < 1:
        raise ValueError("Filename limit cannot preserve the game ID")
    safe_title = safe_title[:remaining].rstrip(" .")
    if not safe_title:
        raise ValidationError("The title cannot fit in the OPL filename limit.")
    return f"{fixed}{safe_title}{suffix}"
