from __future__ import annotations

from enum import Enum, auto

from ps2ripper.core.exceptions import ValidationError

RAW_SECTOR_SIZE = 2352
SYNC = b"\x00" + b"\xff" * 10 + b"\x00"


class SectorForm(Enum):
    MODE1 = auto()
    MODE2_FORM1 = auto()
    MODE2_FORM2 = auto()


def identify_sector_form(sector: bytes) -> SectorForm:
    if len(sector) != RAW_SECTOR_SIZE:
        raise ValidationError(f"Expected a 2352-byte raw sector, received {len(sector)} bytes.")
    if sector[:12] != SYNC:
        raise ValidationError("Raw data sector has an invalid sync pattern.")
    mode = sector[15]
    if mode == 1:
        return SectorForm.MODE1
    if mode != 2:
        raise ValidationError(f"Unsupported CD sector mode {mode}.")
    if sector[16:20] != sector[20:24]:
        raise ValidationError("Mode 2 XA sector has mismatched subheader copies.")
    return SectorForm.MODE2_FORM2 if sector[18] & 0x20 else SectorForm.MODE2_FORM1


def extract_2048_user_data(sector: bytes) -> bytes:
    form = identify_sector_form(sector)
    if form is SectorForm.MODE1:
        return sector[16:2064]
    if form is SectorForm.MODE2_FORM1:
        return sector[24:2072]
    raise ValidationError("Mode 2 Form 2 sectors cannot be represented in a 2048-byte ISO.")
