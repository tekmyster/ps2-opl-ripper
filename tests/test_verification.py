import hashlib

import pycdlib
import pytest

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import CancelledError, ValidationError
from ps2ripper.imaging.verification import copy_and_verify, validate_ps2_iso


def test_copy_hash_mismatch_removes_partial_destination(tmp_path):
    source = tmp_path / "source.iso"
    destination = tmp_path / "destination.iso"
    source.write_bytes(b"owned-disc-image")
    with pytest.raises(ValidationError, match="SHA-256"):
        copy_and_verify(source, destination, "0" * 64)
    assert not destination.exists()


def test_cancelled_copy_removes_partial_destination(tmp_path):
    source = tmp_path / "source.iso"
    destination = tmp_path / "destination.iso"
    source.write_bytes(b"x" * 8192)
    token = CancellationToken()
    token.request()
    with pytest.raises(CancelledError):
        copy_and_verify(
            source,
            destination,
            hashlib.sha256(source.read_bytes()).hexdigest(),
            token,
            chunk_size=512,
        )
    assert not destination.exists()


def test_structural_iso_validation_round_trip(tmp_path):
    image = tmp_path / "game.iso"
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, vol_ident="PS2TEST")
    payload = b"BOOT2 = cdrom0:\\SCUS_973.28;1\r\nVER = 1.00\r\n"
    from io import BytesIO

    iso.add_fp(BytesIO(payload), len(payload), iso_path="/SYSTEM.CNF;1")
    iso.write(str(image))
    iso.close()
    assert validate_ps2_iso(image, "SCUS_973.28") == "SCUS_973.28"
