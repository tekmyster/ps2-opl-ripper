import os
import time

import pytest

from ps2ripper.opl.layout import OPL_DIRECTORIES
from ps2ripper.storage.exfat import initialize_vhd
from ps2ripper.windows.device_enumeration import enumerate_volumes
from ps2ripper.windows.native import is_elevated
from ps2ripper.windows.virtual_disk import AttachedVirtualDisk

pytestmark = pytest.mark.skipif(
    os.environ.get("PS2RIPPER_RUN_VHD_TESTS") != "1" or not is_elevated(),
    reason="Set PS2RIPPER_RUN_VHD_TESTS=1 in an elevated process",
)


def test_windows_mounts_formatted_vhd_without_repair(tmp_path):
    path = tmp_path / "opl-integration.vhd"
    initialize_vhd(path, 512 * 1024**2)

    def wait_for_mount(attached):
        deadline = time.monotonic() + 20
        mounted = None
        while time.monotonic() < deadline:
            mounted = next(
                (
                    volume
                    for volume in enumerate_volumes()
                    if attached.disk_number in volume.disk_numbers and volume.mount_points
                ),
                None,
            )
            if mounted:
                break
            time.sleep(0.25)
        return mounted

    with AttachedVirtualDisk(path) as attached:
        mounted = wait_for_mount(attached)
        assert mounted is not None
        assert mounted.filesystem.casefold() == "exfat"
        root = mounted.mount_points[0]
        assert set(os.listdir(root)) >= set(OPL_DIRECTORIES)
        marker = os.path.join(root, "CFG", "mount-test.bin")
        with open(marker, "xb") as output:
            output.write(b"PS2Ripper Windows mount acceptance\n" * 4096)

    # Detach/reattach exercises the same remount path as a USB disconnect and
    # confirms that Windows persisted the filesystem without a repair step.
    with AttachedVirtualDisk(path) as attached:
        mounted = wait_for_mount(attached)
        assert mounted is not None
        marker = os.path.join(mounted.mount_points[0], "CFG", "mount-test.bin")
        with open(marker, "rb") as source:
            assert source.read(9) == b"PS2Ripper"
