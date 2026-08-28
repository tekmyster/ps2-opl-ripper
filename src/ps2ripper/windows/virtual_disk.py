from __future__ import annotations

import ctypes
import re
import uuid
from ctypes import wintypes
from pathlib import Path

from ps2ripper.core.exceptions import NativeCallError

from .native import GUID, WinHandle, format_win32_error

virtdisk = ctypes.WinDLL("virtdisk", use_last_error=True)

VIRTUAL_DISK_ACCESS_ATTACH_RW = 0x00020000
VIRTUAL_DISK_ACCESS_DETACH = 0x00040000
VIRTUAL_DISK_ACCESS_GET_INFO = 0x00080000
OPEN_VIRTUAL_DISK_VERSION_1 = 1
ATTACH_VIRTUAL_DISK_VERSION_1 = 1
VIRTUAL_STORAGE_TYPE_DEVICE_VHD = 2
MICROSOFT_VIRTUAL_STORAGE_VENDOR = uuid.UUID("ec984aec-a0f9-47e9-901f-71415a66345b")


class VIRTUAL_STORAGE_TYPE(ctypes.Structure):
    _fields_ = [("DeviceId", wintypes.ULONG), ("VendorId", GUID)]


class OPEN_VIRTUAL_DISK_VERSION3(ctypes.Structure):
    _fields_ = [
        ("GetInfoOnly", wintypes.BOOL),
        ("ReadOnly", wintypes.BOOL),
        ("ResiliencyGuid", GUID),
        ("SnapshotId", GUID),
    ]


class OPEN_VIRTUAL_DISK_UNION(ctypes.Union):
    _fields_ = [
        ("RWDepth", wintypes.ULONG),
        ("Version3", OPEN_VIRTUAL_DISK_VERSION3),
    ]


class OPEN_VIRTUAL_DISK_PARAMETERS(ctypes.Structure):
    _anonymous_ = ("Parameters",)
    _fields_ = [("Version", wintypes.ULONG), ("Parameters", OPEN_VIRTUAL_DISK_UNION)]


class ATTACH_VIRTUAL_DISK_UNION(ctypes.Union):
    _fields_ = [("Reserved", wintypes.ULONG), ("Restricted", ctypes.c_ulonglong * 2)]


class ATTACH_VIRTUAL_DISK_PARAMETERS(ctypes.Structure):
    _anonymous_ = ("Parameters",)
    _fields_ = [("Version", wintypes.ULONG), ("Parameters", ATTACH_VIRTUAL_DISK_UNION)]


def _check_status(operation: str, status: int) -> None:
    if status:
        raise NativeCallError(operation, status, format_win32_error(status))


virtdisk.OpenVirtualDisk.argtypes = [
    ctypes.POINTER(VIRTUAL_STORAGE_TYPE),
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(OPEN_VIRTUAL_DISK_PARAMETERS),
    ctypes.POINTER(wintypes.HANDLE),
]
virtdisk.OpenVirtualDisk.restype = wintypes.DWORD
virtdisk.AttachVirtualDisk.argtypes = [
    wintypes.HANDLE,
    ctypes.c_void_p,
    wintypes.DWORD,
    wintypes.ULONG,
    ctypes.POINTER(ATTACH_VIRTUAL_DISK_PARAMETERS),
    ctypes.c_void_p,
]
virtdisk.AttachVirtualDisk.restype = wintypes.DWORD
virtdisk.DetachVirtualDisk.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.ULONG]
virtdisk.DetachVirtualDisk.restype = wintypes.DWORD
virtdisk.GetVirtualDiskPhysicalPath.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(wintypes.ULONG),
    wintypes.LPWSTR,
]
virtdisk.GetVirtualDiskPhysicalPath.restype = wintypes.DWORD


class AttachedVirtualDisk:
    def __init__(self, path: Path) -> None:
        storage_type = VIRTUAL_STORAGE_TYPE(
            VIRTUAL_STORAGE_TYPE_DEVICE_VHD,
            GUID.from_uuid(MICROSOFT_VIRTUAL_STORAGE_VENDOR),
        )
        parameters = OPEN_VIRTUAL_DISK_PARAMETERS()
        parameters.Version = OPEN_VIRTUAL_DISK_VERSION_1
        parameters.RWDepth = 1
        handle = wintypes.HANDLE()
        _check_status(
            "OpenVirtualDisk",
            virtdisk.OpenVirtualDisk(
                ctypes.byref(storage_type),
                str(path.resolve()),
                VIRTUAL_DISK_ACCESS_ATTACH_RW
                | VIRTUAL_DISK_ACCESS_DETACH
                | VIRTUAL_DISK_ACCESS_GET_INFO,
                0,
                ctypes.byref(parameters),
                ctypes.byref(handle),
            ),
        )
        self.handle = WinHandle(handle.value, str(path))
        self.attached = False

    def attach(self) -> AttachedVirtualDisk:
        parameters = ATTACH_VIRTUAL_DISK_PARAMETERS()
        parameters.Version = ATTACH_VIRTUAL_DISK_VERSION_1
        _check_status(
            "AttachVirtualDisk",
            virtdisk.AttachVirtualDisk(
                self.handle.value, None, 0, 0, ctypes.byref(parameters), None
            ),
        )
        self.attached = True
        return self

    @property
    def physical_path(self) -> str:
        size = wintypes.ULONG(2048)
        buffer = ctypes.create_unicode_buffer(size.value // ctypes.sizeof(wintypes.WCHAR))
        _check_status(
            "GetVirtualDiskPhysicalPath",
            virtdisk.GetVirtualDiskPhysicalPath(self.handle.value, ctypes.byref(size), buffer),
        )
        return buffer.value

    @property
    def disk_number(self) -> int:
        match = re.search(r"PhysicalDrive(\d+)$", self.physical_path, re.IGNORECASE)
        if not match:
            raise RuntimeError(f"Unexpected virtual disk path: {self.physical_path}")
        return int(match.group(1))

    def close(self) -> None:
        if self.attached:
            _check_status("DetachVirtualDisk", virtdisk.DetachVirtualDisk(self.handle.value, 0, 0))
            self.attached = False
        self.handle.close()

    def __enter__(self) -> AttachedVirtualDisk:
        return self.attach()

    def __exit__(self, *_: object) -> None:
        self.close()


assert ctypes.sizeof(VIRTUAL_STORAGE_TYPE) == 20
assert ctypes.sizeof(OPEN_VIRTUAL_DISK_PARAMETERS) == 44
assert ctypes.sizeof(ATTACH_VIRTUAL_DISK_PARAMETERS) == 24
