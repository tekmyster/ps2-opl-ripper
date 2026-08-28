from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.core.models import MediaType
from ps2ripper.ps2.naming import opl_iso_filename

OPL_DIRECTORIES = ("DVD", "CD", "ART", "CFG", "VMC", "CHT", "THM", "LNG", "APPS")


@dataclass(frozen=True)
class OPLValidation:
    compatible: bool
    reasons: tuple[str, ...]


class OPLDrive:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def create_directories(self) -> tuple[Path, ...]:
        created: list[Path] = []
        for name in OPL_DIRECTORIES:
            path = self.root / name
            if not path.exists():
                path.mkdir()
                created.append(path)
            elif not path.is_dir():
                raise ValidationError(f"{path} exists but is not a directory.")
        return tuple(created)

    def destination_for_game(self, media_type: MediaType, game_id: str, title: str) -> Path:
        if media_type in (MediaType.PS2_DVD5, MediaType.PS2_DVD9):
            folder = "DVD"
        elif media_type is MediaType.PS2_CD:
            folder = "CD"
        else:
            raise ValidationError("Only recognized PS2 CD/DVD media can be installed.")
        destination = (self.root / folder / opl_iso_filename(game_id, title)).resolve()
        if os.path.commonpath((str(self.root), str(destination))) != str(self.root):
            raise ValidationError("Destination escaped the selected OPL drive.")
        return destination

    def verify_free_space(self, required_bytes: int) -> None:
        free = shutil.disk_usage(self.root).free
        if free < required_bytes:
            raise ValidationError(
                f"The destination needs {required_bytes:,} bytes but only {free:,} are free."
            )
