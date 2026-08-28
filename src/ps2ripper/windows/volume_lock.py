from __future__ import annotations

from contextlib import AbstractContextManager, suppress

from ps2ripper.core.exceptions import UnsafeDeviceError
from ps2ripper.core.models import VolumeInfo

from .native import (
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    FSCTL_DISMOUNT_VOLUME,
    FSCTL_LOCK_VOLUME,
    FSCTL_UNLOCK_VOLUME,
    GENERIC_READ,
    GENERIC_WRITE,
    WinHandle,
    device_io_control,
)


class LockedVolumes(AbstractContextManager["LockedVolumes"]):
    """Lock every volume first, then dismount every volume, retaining all handles."""

    def __init__(self, volumes: tuple[VolumeInfo, ...]) -> None:
        self.volumes = volumes
        self.handles: list[WinHandle] = []

    def __enter__(self) -> LockedVolumes:
        try:
            for volume in self.volumes:
                path = (
                    volume.guid_path[:-1] if volume.guid_path.endswith("\\") else volume.guid_path
                )
                handle = WinHandle.open(
                    path,
                    GENERIC_READ | GENERIC_WRITE,
                    FILE_SHARE_READ | FILE_SHARE_WRITE,
                )
                try:
                    device_io_control(
                        handle, FSCTL_LOCK_VOLUME, operation=f"Lock {volume.guid_path}"
                    )
                except BaseException:
                    handle.close()
                    raise
                self.handles.append(handle)
            for volume, handle in zip(self.volumes, self.handles, strict=True):
                device_io_control(
                    handle, FSCTL_DISMOUNT_VOLUME, operation=f"Dismount {volume.guid_path}"
                )
            return self
        except BaseException as exc:
            self._release()
            raise UnsafeDeviceError(
                "Unable to obtain exclusive access to every volume on the selected disk. "
                "Close applications using the drive and try again."
            ) from exc

    def _release(self) -> None:
        for handle in reversed(self.handles):
            with suppress(OSError):
                device_io_control(handle, FSCTL_UNLOCK_VOLUME, operation="Unlock volume")
            handle.close()
        self.handles.clear()

    def __exit__(self, *_: object) -> None:
        self._release()
