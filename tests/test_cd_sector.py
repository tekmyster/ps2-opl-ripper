import pytest

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.imaging.cd_sector import RAW_SECTOR_SIZE, SYNC, extract_2048_user_data


def make_sector(mode: int, payload: bytes, form2: bool = False) -> bytes:
    sector = bytearray(RAW_SECTOR_SIZE)
    sector[:12] = SYNC
    sector[15] = mode
    if mode == 1:
        sector[16 : 16 + len(payload)] = payload
    else:
        subheader = bytes((1, 2, 0x20 if form2 else 0, 4))
        sector[16:20] = subheader
        sector[20:24] = subheader
        sector[24 : 24 + len(payload)] = payload
    return bytes(sector)


def test_extracts_mode1():
    payload = bytes(range(256)) * 8
    assert extract_2048_user_data(make_sector(1, payload)) == payload


def test_extracts_mode2_form1():
    payload = b"x" * 2048
    assert extract_2048_user_data(make_sector(2, payload)) == payload


def test_rejects_mode2_form2():
    with pytest.raises(ValidationError, match="Form 2"):
        extract_2048_user_data(make_sector(2, b"x" * 2048, form2=True))
