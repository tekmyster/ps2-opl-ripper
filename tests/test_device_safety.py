import pytest

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import UnsafeDeviceError
from ps2ripper.core.models import PartitionInfo, PartitionStyle, PhysicalDisk, VolumeInfo
from ps2ripper.windows.device_enumeration import validate_opl_compatibility, verify_same_identity
from ps2ripper.windows.storage_api import PhysicalDiskManager


def compatible_disk(**changes):
    values = dict(
        number=3,
        device_path=r"\\.\PhysicalDrive3",
        instance_id="USBSTOR\\DISK&VEN_TEST",
        model="Test disk",
        bus_type="USB",
        capacity=64 * 1024**3,
        usb=True,
        partition_style=PartitionStyle.MBR,
        partitions=(PartitionInfo(1, 1024 * 1024, 63 * 1024**3, PartitionStyle.MBR),),
        volumes=(
            VolumeInfo(
                r"\\?\Volume{test}\\",
                ("E:\\",),
                "exFAT",
                writable=True,
                disk_numbers=(3,),
            ),
        ),
    )
    values.update(changes)
    return PhysicalDisk(**values)


def test_compatible_mbr_exfat_disk():
    assert validate_opl_compatibility(compatible_disk()) == (True, ())


def test_gpt_is_not_compatible():
    compatible, reasons = validate_opl_compatibility(
        compatible_disk(partition_style=PartitionStyle.GPT)
    )
    assert not compatible
    assert "not MBR" in reasons[0]


def test_exfat_volume_without_mount_point_is_not_ready():
    compatible, reasons = validate_opl_compatibility(
        compatible_disk(
            volumes=(
                VolumeInfo(
                    "\\\\?\\Volume{test}\\",
                    (),
                    "exFAT",
                    writable=True,
                    disk_numbers=(3,),
                ),
            )
        )
    )
    assert not compatible
    assert "no accessible mount point" in reasons[0]


def test_identity_change_is_rejected():
    selected = compatible_disk(serial="one")
    current = compatible_disk(serial="two")
    try:
        verify_same_identity(selected, current)
    except RuntimeError as exc:
        assert "no longer matches" in str(exc)
    else:
        raise AssertionError("identity change was not rejected")


def test_disk_disappearance_is_reported_before_destructive_access():
    class MissingDiskManager(PhysicalDiskManager):
        def enumerate_usb_disks(self):
            return ()

    with pytest.raises(UnsafeDeviceError, match="no longer connected"):
        MissingDiskManager()._current_identity(compatible_disk())


def test_typed_confirmation_requires_physical_disk_number():
    with pytest.raises(UnsafeDeviceError, match="ERASE PHYSICALDRIVE 3"):
        PhysicalDiskManager().initialize_mbr_exfat(compatible_disk(), "YES", CancellationToken())
