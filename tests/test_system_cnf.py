import pytest

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.ps2.system_cnf import normalize_game_id, parse_system_cnf


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (r"cdrom0:\\SLUS_203.12;1", "SLUS_203.12"),
        (r"CDROM0:\\scus-971.24;1", "SCUS_971.24"),
        (r"mass:\\SLES_544.39", "SLES_544.39"),
    ],
)
def test_normalize_game_id(value, expected):
    assert normalize_game_id(value) == expected


def test_parse_system_cnf_prefers_boot2():
    parsed = parse_system_cnf(b"BOOT = cdrom:\\ABCD_000.01;1\r\nBOOT2 = cdrom0:\\SCUS_973.28;1\r\n")
    assert parsed.game_id == "SCUS_973.28"
    assert parsed.values["BOOT2"].startswith("cdrom0")


def test_parse_system_cnf_rejects_missing_boot():
    with pytest.raises(ValidationError):
        parse_system_cnf("VER = 1.00")
