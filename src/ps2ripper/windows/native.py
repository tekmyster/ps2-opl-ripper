from __future__ import annotations

import ctypes
import sys
import uuid
from ctypes import wintypes
from typing import Final

from ps2ripper.core.exceptions import NativeCallError

if sys.platform != "win32":
    raise ImportError("ps2ripper.windows is available only on Windows")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
MAX_PATH = 260

GENERIC_READ: Final = 0x80000000
GENERIC_WRITE: Final = 0x40000000
FILE_SHARE_READ: Final = 0x00000001
FILE_SHARE_WRITE: Final = 0x00000002
OPEN_EXISTING: Final = 3
FILE_ATTRIBUTE_NORMAL: Final = 0x80
FILE_FLAG_WRITE_THROUGH: Final = 0x80000000

DIGCF_PRESENT: Final = 0x00000002
DIGCF_DEVICEINTERFACE: Final = 0x00000010
SPDRP_DEVICEDESC: Final = 0
SPDRP_HARDWAREID: Final = 1
SPDRP_MFG: Final = 11
SPDRP_FRIENDLYNAME: Final = 12

ERROR_INSUFFICIENT_BUFFER: Final = 122
ERROR_NO_MORE_ITEMS: Final = 259

IOCTL_STORAGE_QUERY_PROPERTY: Final = 0x002D1400
IOCTL_STORAGE_GET_DEVICE_NUMBER: Final = 0x002D1080
IOCTL_STORAGE_EJECT_MEDIA: Final = 0x002D4808
IOCTL_DISK_GET_DRIVE_LAYOUT_EX: Final = 0x00070050
IOCTL_DISK_GET_LENGTH_INFO: Final = 0x0007405C
IOCTL_DISK_UPDATE_PROPERTIES: Final = 0x00070140
IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS: Final = 0x00560000
FSCTL_LOCK_VOLUME: Final = 0x00090018
FSCTL_UNLOCK_VOLUME: Final = 0x0009001C
FSCTL_DISMOUNT_VOLUME: Final = 0x00090020
IOCTL_SCSI_PASS_THROUGH_DIRECT: Final = 0x0004D014
IOCTL_DVD_READ_STRUCTURE: Final = 0x00335140

GUID_DEVINTERFACE_DISK = uuid.UUID("53f56307-b6bf-11d0-94f2-00a0c91efb8b")
GUID_DEVINTERFACE_CDROM = uuid.UUID("53f56308-b6bf-11d0-94f2-00a0c91efb8b")


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def from_uuid(cls, value: uuid.UUID) -> GUID:
        raw = value.bytes_le
        result = cls()
        ctypes.memmove(ctypes.byref(result), raw, 16)
        return result


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_size_t),
    ]


class STORAGE_PROPERTY_QUERY(ctypes.Structure):
    _fields_ = [
        ("PropertyId", wintypes.DWORD),
        ("QueryType", wintypes.DWORD),
        ("AdditionalParameters", ctypes.c_ubyte * 1),
    ]


class STORAGE_DEVICE_NUMBER(ctypes.Structure):
    _fields_ = [
        ("DeviceType", wintypes.DWORD),
        ("DeviceNumber", wintypes.DWORD),
        ("PartitionNumber", wintypes.DWORD),
    ]


class SCSI_PASS_THROUGH_DIRECT(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("ScsiStatus", ctypes.c_ubyte),
        ("PathId", ctypes.c_ubyte),
        ("TargetId", ctypes.c_ubyte),
        ("Lun", ctypes.c_ubyte),
        ("CdbLength", ctypes.c_ubyte),
        ("SenseInfoLength", ctypes.c_ubyte),
        ("DataIn", ctypes.c_ubyte),
        ("DataTransferLength", wintypes.ULONG),
        ("TimeOutValue", wintypes.ULONG),
        ("DataBuffer", ctypes.c_void_p),
        ("SenseInfoOffset", wintypes.ULONG),
        ("Cdb", ctypes.c_ubyte * 16),
    ]


class SPTD_WITH_SENSE(ctypes.Structure):
    _fields_ = [("sptd", SCSI_PASS_THROUGH_DIRECT), ("sense", ctypes.c_ubyte * 32)]


def _configure_prototypes() -> None:
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.DeviceIoControl.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.FindFirstVolumeW.argtypes = [wintypes.LPWSTR, wintypes.DWORD]
    kernel32.FindFirstVolumeW.restype = wintypes.HANDLE
    kernel32.FindNextVolumeW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD]
    kernel32.FindNextVolumeW.restype = wintypes.BOOL
    kernel32.FindVolumeClose.argtypes = [wintypes.HANDLE]
    kernel32.FindVolumeClose.restype = wintypes.BOOL
    kernel32.GetVolumePathNamesForVolumeNameW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    kernel32.GetVolumePathNamesForVolumeNameW.restype = wintypes.BOOL
    kernel32.GetVolumeInformationW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeInformationW.restype = wintypes.BOOL
    kernel32.GetWindowsDirectoryW.argtypes = [wintypes.LPWSTR, wintypes.UINT]
    kernel32.GetWindowsDirectoryW.restype = wintypes.UINT
    kernel32.GetVolumePathNameW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD]
    kernel32.GetVolumePathNameW.restype = wintypes.BOOL
    kernel32.GetVolumeNameForVolumeMountPointW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.GetVolumeNameForVolumeMountPointW.restype = wintypes.BOOL
    kernel32.GetLogicalDrives.restype = wintypes.DWORD
    kernel32.GetDriveTypeW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetDriveTypeW.restype = wintypes.UINT
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = kernel32.ReadFile.argtypes
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    setupapi.SetupDiGetClassDevsW.restype = wintypes.HANDLE
    setupapi.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(GUID),
        wintypes.LPCWSTR,
        wintypes.HWND,
        wintypes.DWORD,
    ]
    setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        ctypes.POINTER(GUID),
        wintypes.DWORD,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
    ]
    setupapi.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(SP_DEVINFO_DATA),
    ]
    setupapi.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceRegistryPropertyW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    setupapi.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
    setupapi.SetupDiGetDeviceInstanceIdW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(SP_DEVINFO_DATA),
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    setupapi.SetupDiDestroyDeviceInfoList.argtypes = [wintypes.HANDLE]
    setupapi.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    shell32.IsUserAnAdmin.restype = wintypes.BOOL


_configure_prototypes()


def format_win32_error(code: int | None = None) -> str:
    error = ctypes.get_last_error() if code is None else code
    return ctypes.FormatError(error).strip() or "Unknown Windows error"


def raise_last_error(operation: str) -> None:
    code = ctypes.get_last_error()
    raise NativeCallError(operation, code, format_win32_error(code))


class WinHandle:
    def __init__(self, value: int, name: str) -> None:
        if value in (None, 0, INVALID_HANDLE_VALUE):
            raise_last_error(f"Open {name}")
        self.value = value
        self.name = name

    @classmethod
    def open(
        cls,
        path: str,
        access: int = GENERIC_READ,
        share: int = FILE_SHARE_READ | FILE_SHARE_WRITE,
        flags: int = FILE_ATTRIBUTE_NORMAL,
    ) -> WinHandle:
        value = kernel32.CreateFileW(path, access, share, None, OPEN_EXISTING, flags, None)
        return cls(value, path)

    def close(self) -> None:
        if self.value not in (None, 0, INVALID_HANDLE_VALUE):
            kernel32.CloseHandle(self.value)
            self.value = None

    def __enter__(self) -> WinHandle:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def device_io_control(
    handle: WinHandle,
    code: int,
    in_buffer: object | None = None,
    out_size: int = 0,
    operation: str = "DeviceIoControl",
) -> bytes:
    if in_buffer is None:
        in_pointer = None
        in_size = 0
    elif isinstance(in_buffer, bytes):
        in_object = ctypes.create_string_buffer(in_buffer)
        in_pointer = ctypes.byref(in_object)
        in_size = len(in_buffer)
    else:
        in_object = in_buffer
        in_pointer = ctypes.byref(in_object)
        in_size = ctypes.sizeof(in_object)
    output = ctypes.create_string_buffer(out_size) if out_size else None
    returned = wintypes.DWORD()
    ok = kernel32.DeviceIoControl(
        handle.value,
        code,
        in_pointer,
        in_size,
        output,
        out_size,
        ctypes.byref(returned),
        None,
    )
    if not ok:
        raise_last_error(operation)
    return output.raw[: returned.value] if output is not None else b""


def is_elevated() -> bool:
    return bool(shell32.IsUserAnAdmin())


def human_size(size: int) -> str:
    value = float(size)
    for unit in ("bytes", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024.0 or unit == "TiB":
            return f"{value:.2f} {unit}" if unit != "bytes" else f"{size} bytes"
        value /= 1024.0
    return f"{size} bytes"


assert ctypes.sizeof(SP_DEVICE_INTERFACE_DATA) == 32
assert ctypes.sizeof(SP_DEVINFO_DATA) == 32
assert ctypes.sizeof(STORAGE_PROPERTY_QUERY) == 12
assert ctypes.sizeof(STORAGE_DEVICE_NUMBER) == 12
assert ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT) == 56
assert SCSI_PASS_THROUGH_DIRECT.DataBuffer.offset == 24
assert ctypes.sizeof(SPTD_WITH_SENSE) == 88
