import pytest

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import OpticalReadError
from ps2ripper.imaging.ripper import rip_dvd_iso


class FakeReader:
    def __init__(self, fail_lba=None):
        self.fail_lba = fail_lba

    def read_blocks(self, lba, count, sector_size=2048):
        if self.fail_lba is not None and lba <= self.fail_lba < lba + count:
            raise OSError("synthetic read error")
        return b"".join(bytes([sector % 251]) * 2048 for sector in range(lba, lba + count))


def test_dvd_rip_hashes_complete_image(tmp_path):
    result = rip_dvd_iso(FakeReader(), tmp_path / "game.iso", 65, CancellationToken())
    assert result.size == 65 * 2048
    assert result.complete
    assert len(result.sha256) == 64


def test_dvd_rip_aborts_and_removes_partial_image(tmp_path):
    path = tmp_path / "game.iso"
    with pytest.raises(OpticalReadError):
        rip_dvd_iso(FakeReader(10), path, 20, CancellationToken(), chunk_sectors=16, max_retries=2)
    assert not path.exists()
