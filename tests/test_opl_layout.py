from ps2ripper.core.models import MediaType
from ps2ripper.opl.layout import OPL_DIRECTORIES, OPLDrive


def test_creates_missing_folders_without_deleting_existing(tmp_path):
    existing = tmp_path / "DVD"
    existing.mkdir()
    marker = existing / "keep.txt"
    marker.write_text("keep")
    created = OPLDrive(tmp_path).create_directories()
    assert marker.read_text() == "keep"
    assert {path.name for path in created} == set(OPL_DIRECTORIES) - {"DVD"}


def test_destination_uses_media_folder(tmp_path):
    drive = OPLDrive(tmp_path)
    assert drive.destination_for_game(MediaType.PS2_DVD9, "SCUS_973.28", "God of War").name == (
        "SCUS_973.28.God of War.iso"
    )
    assert drive.destination_for_game(MediaType.PS2_CD, "SLUS_000.00", "Demo").parent.name == "CD"
