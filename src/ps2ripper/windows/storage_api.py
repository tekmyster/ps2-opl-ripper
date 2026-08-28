from __future__ import annotations

import time

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import UnsafeDeviceError, ValidationError
from ps2ripper.core.models import PhysicalDisk
from ps2ripper.storage.exfat import FormatResult, initialize_stream

from .device_enumeration import enumerate_physical_disks, verify_same_identity
from .native import (
    FILE_FLAG_WRITE_THROUGH,
    GENERIC_READ,
    GENERIC_WRITE,
    IOCTL_DISK_UPDATE_PROPERTIES,
    WinHandle,
    device_io_control,
)
from .raw_disk import RawDiskStream
from .volume_lock import LockedVolumes


def expected_erase_confirmation(disk: PhysicalDisk) -> str:
    return f"ERASE PHYSICALDRIVE {disk.number}"


class PhysicalDiskManager:
    def enumerate_usb_disks(self) -> tuple[PhysicalDisk, ...]:
        return enumerate_physical_disks(usb_only=True)

    def _current_identity(self, selected: PhysicalDisk) -> PhysicalDisk:
        current = next(
            (disk for disk in self.enumerate_usb_disks() if disk.number == selected.number), None
        )
        if current is None:
            raise UnsafeDeviceError(f"{selected.physical_name} is no longer connected.")
        verify_same_identity(selected, current)
        return current

    def initialize_mbr_exfat(
        self,
        selected: PhysicalDisk,
        typed_confirmation: str,
        token: CancellationToken,
    ) -> FormatResult:
        expected = expected_erase_confirmation(selected)
        if typed_confirmation.strip().upper() != expected:
            raise UnsafeDeviceError(f"Confirmation must exactly match: {expected}")
        if selected.safety_reasons:
            raise UnsafeDeviceError(
                "Destructive access is blocked: " + " ".join(selected.safety_reasons)
            )
        token.checkpoint()
        current = self._current_identity(selected)
        with LockedVolumes(current.volumes):
            # Required last-moment identity check after locks are held and before
            # the first partition-table byte can be written.
            current = self._current_identity(selected)
            if current.safety_reasons:
                raise UnsafeDeviceError(
                    "Destructive access became unsafe: " + " ".join(current.safety_reasons)
                )
            with WinHandle.open(
                current.device_path,
                GENERIC_READ | GENERIC_WRITE,
                share=0,
                flags=FILE_FLAG_WRITE_THROUGH,
            ) as handle:
                stream = RawDiskStream(handle, current.capacity, current.logical_sector_size)
                with token.critical_section(checkpoint_on_exit=False):
                    result = initialize_stream(stream)
                    stream.flush()
                    device_io_control(
                        handle,
                        IOCTL_DISK_UPDATE_PROPERTIES,
                        operation="IOCTL_DISK_UPDATE_PROPERTIES",
                    )
                return result

    def wait_for_remount(
        self,
        selected: PhysicalDisk,
        token: CancellationToken,
        timeout_seconds: float = 30.0,
        honor_cancellation: bool = True,
    ) -> PhysicalDisk:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if honor_cancellation:
                token.checkpoint()
            current = self._current_identity(selected)
            if current.volumes:
                return current
            time.sleep(0.5)
        raise ValidationError(
            f"{selected.physical_name} did not remount in Windows within {timeout_seconds:.0f} seconds."
        )
