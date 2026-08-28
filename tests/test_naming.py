import pytest

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.ps2.naming import opl_iso_filename, sanitize_title


def test_sanitizes_windows_characters_and_trailing_periods():
    assert sanitize_title("  God: of / War...  ") == "God of War"


def test_reserved_dos_name_is_made_safe():
    assert sanitize_title("CON") == "CON Game"


def test_filename_preserves_id_when_truncated():
    result = opl_iso_filename("SCUS_973.28", "A" * 300)
    assert result.startswith("SCUS_973.28.")
    assert result.endswith(".iso")
    assert len(result) == 160


def test_empty_title_is_rejected():
    with pytest.raises(ValidationError):
        sanitize_title("<>...")
