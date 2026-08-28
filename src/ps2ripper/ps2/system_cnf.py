from __future__ import annotations

import re
from dataclasses import dataclass

from ps2ripper.core.exceptions import ValidationError

_ASSIGNMENT = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
_GAME_ID = re.compile(r"(?<![A-Z0-9])([A-Z]{4}[-_]\d{3}\.\d{2})(?!\d)", re.IGNORECASE)


@dataclass(frozen=True)
class SystemCnf:
    values: dict[str, str]
    boot_path: str
    game_id: str


def normalize_game_id(value: str) -> str:
    match = _GAME_ID.search(value)
    if not match:
        raise ValidationError("No recognizable PS2 executable ID was found.")
    return match.group(1).upper().replace("-", "_")


def parse_system_cnf(data: bytes | str) -> SystemCnf:
    if isinstance(data, bytes):
        if len(data) > 1024 * 1024:
            raise ValidationError("SYSTEM.CNF is implausibly large.")
        text = data.decode("ascii", "replace")
    else:
        text = data

    values: dict[str, str] = {}
    for raw_line in text.replace("\r", "\n").split("\n"):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        match = _ASSIGNMENT.match(line)
        if match:
            values[match.group(1).upper()] = match.group(2).strip()

    boot_path = values.get("BOOT2") or values.get("BOOT")
    if not boot_path:
        raise ValidationError("SYSTEM.CNF does not contain BOOT2 or BOOT.")
    return SystemCnf(values=values, boot_path=boot_path, game_id=normalize_game_id(boot_path))
