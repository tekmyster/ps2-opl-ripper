from __future__ import annotations

import ctypes
import logging
import re
import struct
import uuid
from ctypes import wintypes
from dataclasses import replace

from ps2ripper.core.models import (
    PartitionInfo,
    PartitionStyle,
    PhysicalDisk,
    VolumeInfo,
)

from .native import (
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GUID_DEVINTERFACE_DISK,
    IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
    IOCTL_DISK_GET_LENGTH_INFO,
    IOCTL_STORAGE_GET_DEVICE_NUMBER,
    IOCTL_STORAGE_QUERY_PROPERTY,
    IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
    SPDRP_DEVICEDESC,
    SPDRP_FRIENDLYNAME,
    SPDRP_MFG,
    STORAGE_DEVICE_NUMBER,
    STORAGE_PROPERTY_QUERY,
    WinHandle,
    device_io_control,
    kernel32,
)
from .setup_devices import enumerate_device_interfaces

logger = logging.getLogger(__name__)

FILE_READ_ONLY_VOLUME = 0x00080000
PARTITION_STYLE_MBR = 0
PARTITION_STYLE_GPT = 1
PARTITION_STYLE_RAW = 2
MBR_MAX_512_BYTES = 0xFFFFFFFF * 512

EFI_SYSTEM = uuid.UUID("c12a7328-f81f-11d2-ba4b-00a0c93ec93b")
MS_RESERVED = uuid.UUID("e3c9e316-0b5c-4db8-817d-f92df00215ae")
MS_RECOVERY = uuid.UUID("de94bba4-06d1-4d40-a16a-bfd50179d6ac")

BUS_TYPES = {
    0: "Unknown",
    1: "SCSI",
    2: "ATAPI",
    3: "ATA",
    4: "IEEE 1394",
    7: "USB",
    8: "RAID",
    9: "iSCSI",
    10: "SAS",
    11: "SATA",
    12: "SD",
    13: "MMC",
    14: "Virtual",
    15: "File-backed virtual",
    16: "Storage Spaces",
    17: "NVMe",
    18: "SCM",
    19: "UFS",
}


def _decode_descriptor_string(data: bytes, offset: int) -> str:
    if not offset or offset >= len(data):
        return ""
    end = data.find(b"\0", offset)
    raw = data[offset : end if end >= 0 else len(data)]
    return raw.decode("ascii", "replace").strip()


def _query_storage_device(handle: WinHandle) -> dict[str, object]:
    query = STORAGE_PROPERTY_QUERY(PropertyId=0, QueryType=0)
    header = device_io_control(
        handle, IOCTL_STORAGE_QUERY_PROPERTY, query, 8, "StorageDeviceProperty"
    )
    if len(header) < 8:
        raise OSError("Storage descriptor header was truncated")
    size = min(max(struct.unpack_from("<I", header, 4)[0], 40), 1024 * 1024)
    data = device_io_control(
        handle, IOCTL_STORAGE_QUERY_PROPERTY, query, size, "StorageDeviceProperty"
    )
    if len(data) < 36:
        raise OSError("Storage device descriptor was truncated")
    return {
        "removable": bool(data[10]),
        "vendor": _decode_descriptor_string(data, struct.unpack_from("<I", data, 12)[0]),
        "product": _decode_descriptor_string(data, struct.unpack_from("<I", data, 16)[0]),
        "revision": _decode_descriptor_string(data, struct.unpack_from("<I", data, 20)[0]),
        "serial": _decode_descriptor_string(data, struct.unpack_from("<I", data, 24)[0]),
        "bus_number": struct.unpack_from("<I", data, 28)[0],
    }


def _query_logical_sector_size(handle: WinHandle) -> int:
    query = STORAGE_PROPERTY_QUERY(PropertyId=6, QueryType=0)
    try:
        data = device_io_control(
            handle, IOCTL_STORAGE_QUERY_PROPERTY, query, 64, "StorageAccessAlignmentProperty"
        )
        if len(data) >= 28:
            return struct.unpack_from("<I", data, 16)[0] or 512
    except OSError:
        logger.debug("StorageAccessAlignmentProperty unavailable", exc_info=True)
    return 512


def _query_device_number(handle: WinHandle) -> int:
    raw = device_io_control(
        handle,
        IOCTL_STORAGE_GET_DEVICE_NUMBER,
        out_size=ctypes.sizeof(STORAGE_DEVICE_NUMBER),
        operation="IOCTL_STORAGE_GET_DEVICE_NUMBER",
    )
    if len(raw) < 12:
        raise OSError("Storage device number was truncated")
    return struct.unpack_from("<I", raw, 4)[0]


def _query_capacity(handle: WinHandle) -> int:
    raw = device_io_control(
        handle, IOCTL_DISK_GET_LENGTH_INFO, out_size=8, operation="IOCTL_DISK_GET_LENGTH_INFO"
    )
    if len(raw) != 8:
        raise OSError("Disk length was truncated")
    return struct.unpack("<Q", raw)[0]


def _query_layout(handle: WinHandle) -> tuple[PartitionStyle, tuple[PartitionInfo, ...]]:
    raw = device_io_control(
        handle,
        IOCTL_DISK_GET_DRIVE_LAYOUT_EX,
        out_size=1024 * 1024,
        operation="IOCTL_DISK_GET_DRIVE_LAYOUT_EX",
    )
    if len(raw) < 48:
        return PartitionStyle.UNKNOWN, ()
    style_value, count = struct.unpack_from("<II", raw, 0)
    style = {
        PARTITION_STYLE_MBR: PartitionStyle.MBR,
        PARTITION_STYLE_GPT: PartitionStyle.GPT,
        PARTITION_STYLE_RAW: PartitionStyle.RAW,
    }.get(style_value, PartitionStyle.UNKNOWN)
    partitions: list[PartitionInfo] = []
    for index in range(min(count, (len(raw) - 48) // 144)):
        offset = 48 + index * 144
        entry_style = struct.unpack_from("<I", raw, offset)[0]
        starting, length, number = struct.unpack_from("<QQI", raw, offset + 8)
        is_boot = False
        is_system = False
        is_recovery = False
        is_efi = False
        type_description = ""
        if entry_style == PARTITION_STYLE_MBR:
            partition_type, boot = struct.unpack_from("<BB", raw, offset + 32)
            is_boot = bool(boot)
            is_efi = partition_type == 0xEF
            is_recovery = partition_type == 0x27
            is_system = is_efi
            type_description = f"MBR type 0x{partition_type:02X}"
        elif entry_style == PARTITION_STYLE_GPT:
            type_guid = uuid.UUID(bytes_le=raw[offset + 32 : offset + 48])
            is_efi = type_guid == EFI_SYSTEM
            is_recovery = type_guid == MS_RECOVERY
            is_system = type_guid in (EFI_SYSTEM, MS_RESERVED)
            type_description = str(type_guid)
        if not number or not length:
            continue
        partitions.append(
            PartitionInfo(
                number=number,
                offset=starting,
                length=length,
                style=style,
                type_description=type_description,
                is_boot=is_boot,
                is_system=is_system,
                is_recovery=is_recovery,
                is_efi=is_efi,
            )
        )
    return style, tuple(partitions)


def _volume_mount_points(volume_name: str) -> tuple[str, ...]:
    required = wintypes.DWORD()
    kernel32.GetVolumePathNamesForVolumeNameW(volume_name, None, 0, ctypes.byref(required))
    if not required.value:
        return ()
    buffer = ctypes.create_unicode_buffer(required.value)
    if not kernel32.GetVolumePathNamesForVolumeNameW(
        volume_name, buffer, required.value, ctypes.byref(required)
    ):
        return ()
    return tuple(part for part in buffer[: required.value].split("\0") if part)


def _volume_filesystem(volume_name: str) -> tuple[str | None, str | None, bool]:
    label = ctypes.create_unicode_buffer(256)
    filesystem = ctypes.create_unicode_buffer(64)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    ok = kernel32.GetVolumeInformationW(
        volume_name,
        label,
        len(label),
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        len(filesystem),
    )
    if not ok:
        return None, None, False
    return (
        filesystem.value or None,
        label.value or None,
        not bool(flags.value & FILE_READ_ONLY_VOLUME),
    )


def _volume_extents(volume_name: str) -> tuple[int, ...]:
    device_path = volume_name[:-1] if volume_name.endswith("\\") else volume_name
    try:
        with WinHandle.open(device_path) as handle:
            raw = device_io_control(
                handle,
                IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS,
                out_size=64 * 1024,
                operation="IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS",
            )
    except OSError:
        logger.debug("Cannot read extents for %s", volume_name, exc_info=True)
        return ()
    if len(raw) < 8:
        return ()
    count = struct.unpack_from("<I", raw, 0)[0]
    return tuple(
        struct.unpack_from("<I", raw, 8 + index * 24)[0]
        for index in range(min(count, (len(raw) - 8) // 24))
    )


def enumerate_volumes() -> tuple[VolumeInfo, ...]:
    buffer = ctypes.create_unicode_buffer(1024)
    find_handle = kernel32.FindFirstVolumeW(buffer, len(buffer))
    if find_handle in (None, 0, ctypes.c_void_p(-1).value):
        return ()
    volumes: list[VolumeInfo] = []
    try:
        while True:
            name = buffer.value
            fs, label, writable = _volume_filesystem(name)
            volumes.append(
                VolumeInfo(
                    guid_path=name,
                    mount_points=_volume_mount_points(name),
                    filesystem=fs,
                    label=label,
                    writable=writable,
                    disk_numbers=_volume_extents(name),
                )
            )
            if not kernel32.FindNextVolumeW(find_handle, buffer, len(buffer)):
                break
    finally:
        kernel32.FindVolumeClose(find_handle)
    return tuple(volumes)


def _volume_name_for_path(path: str) -> str | None:
    root = ctypes.create_unicode_buffer(1024)
    if not kernel32.GetVolumePathNameW(path, root, len(root)):
        return None
    volume = ctypes.create_unicode_buffer(1024)
    if not kernel32.GetVolumeNameForVolumeMountPointW(root.value, volume, len(volume)):
        return None
    return volume.value.casefold()


def _windows_volume_name() -> str | None:
    buffer = ctypes.create_unicode_buffer(32768)
    length = kernel32.GetWindowsDirectoryW(buffer, len(buffer))
    return _volume_name_for_path(buffer.value) if length else None


def _active_pagefile_volumes() -> tuple[set[str], bool]:
    result: set[str] = set()
    try:
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        callback_type = ctypes.WINFUNCTYPE(
            wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p, wintypes.LPCWSTR
        )

        @callback_type
        def callback(_context: int, _info: int, filename: str) -> bool:
            match = re.search(r"([A-Za-z]:\\.*)$", filename or "")
            if match and (volume := _volume_name_for_path(match.group(1))):
                result.add(volume)
            return True

        psapi.EnumPageFilesW.argtypes = [callback_type, ctypes.c_void_p]
        psapi.EnumPageFilesW.restype = wintypes.BOOL
        if not psapi.EnumPageFilesW(callback, None):
            return result, False
    except Exception:
        logger.warning(
            "Unable to enumerate active pagefiles; destructive access will stay conservative"
        )
        return result, False
    return result, True


def _safety_reasons(
    disk: PhysicalDisk,
    windows_volume: str | None,
    pagefile_volumes: set[str],
    pagefile_check_succeeded: bool,
) -> tuple[str, ...]:
    reasons: list[str] = []
    if not disk.usb:
        reasons.append("The device is not reported as USB storage.")
    if not disk.instance_id:
        reasons.append("Windows did not provide a stable device instance identity.")
    if not pagefile_check_succeeded:
        reasons.append("Windows did not allow active-pagefile safety verification.")
    if disk.logical_sector_size != 512:
        reasons.append(
            f"The device uses {disk.logical_sector_size}-byte logical sectors; physical initialization is not verified."
        )
    if disk.capacity > MBR_MAX_512_BYTES:
        reasons.append(
            "The device is too large for a fully addressable 512-byte-sector MBR partition."
        )
    for volume in disk.volumes:
        normalized = volume.guid_path.casefold()
        if windows_volume and normalized == windows_volume:
            reasons.append("The device contains the running Windows installation.")
        if normalized in pagefile_volumes:
            reasons.append("The device contains an active pagefile.")
        if len(volume.disk_numbers) != 1:
            reasons.append("A volume has ambiguous or multi-disk extents.")
    for partition in disk.partitions:
        if partition.is_boot:
            reasons.append(f"Partition {partition.number} is marked boot/active.")
        if partition.is_system:
            reasons.append(f"Partition {partition.number} is a system or reserved partition.")
        if partition.is_efi:
            reasons.append(f"Partition {partition.number} is an EFI system partition.")
        if partition.is_recovery:
            reasons.append(f"Partition {partition.number} is a recovery partition.")
    return tuple(dict.fromkeys(reasons))


def enumerate_physical_disks(usb_only: bool = True) -> tuple[PhysicalDisk, ...]:
    volumes = enumerate_volumes()
    disks: list[PhysicalDisk] = []
    interfaces = enumerate_device_interfaces(
        GUID_DEVINTERFACE_DISK, (SPDRP_FRIENDLYNAME, SPDRP_DEVICEDESC, SPDRP_MFG)
    )
    for interface in interfaces:
        try:
            with WinHandle.open(
                interface.path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE
            ) as handle:
                number = _query_device_number(handle)
                descriptor = _query_storage_device(handle)
                capacity = _query_capacity(handle)
                logical_sector = _query_logical_sector_size(handle)
                style, partitions = _query_layout(handle)
        except OSError as exc:
            logger.warning("Skipping disk interface %s: %s", interface.path, exc)
            continue
        bus_number = int(descriptor["bus_number"])
        bus_type = BUS_TYPES.get(bus_number, f"Bus type {bus_number}")
        is_usb = bus_number == 7 or interface.instance_id.upper().startswith("USBSTOR\\")
        if usb_only and not is_usb:
            continue
        disk_volumes = tuple(volume for volume in volumes if number in volume.disk_numbers)
        model = str(descriptor["product"]) or interface.properties.get(SPDRP_FRIENDLYNAME, "")
        disk = PhysicalDisk(
            number=number,
            device_path=rf"\\.\PhysicalDrive{number}",
            instance_id=interface.instance_id,
            model=model or interface.properties.get(SPDRP_DEVICEDESC, "Unknown disk"),
            manufacturer=str(descriptor["vendor"]) or interface.properties.get(SPDRP_MFG, ""),
            serial=str(descriptor["serial"]),
            bus_type=bus_type,
            capacity=capacity,
            logical_sector_size=logical_sector,
            removable=bool(descriptor["removable"]),
            usb=is_usb,
            partition_style=style,
            partitions=partitions,
            volumes=disk_volumes,
        )
        disks.append(disk)
    windows_volume = _windows_volume_name()
    pagefiles, pagefile_check_succeeded = _active_pagefile_volumes()
    return tuple(
        sorted(
            (
                replace(
                    disk,
                    safety_reasons=_safety_reasons(
                        disk, windows_volume, pagefiles, pagefile_check_succeeded
                    ),
                )
                for disk in disks
            ),
            key=lambda disk: disk.number,
        )
    )


def validate_opl_compatibility(disk: PhysicalDisk) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if disk.partition_style is not PartitionStyle.MBR:
        reasons.append(f"Partition table is {disk.partition_style.name}, not MBR.")
    if len(disk.partitions) != 1:
        reasons.append(f"Expected one primary partition; found {len(disk.partitions)}.")
    if len(disk.volumes) != 1:
        reasons.append(f"Expected one mounted volume; found {len(disk.volumes)}.")
    elif (disk.volumes[0].filesystem or "").casefold() != "exfat":
        reasons.append(f"Filesystem is {disk.volumes[0].filesystem or 'unknown'}, not exFAT.")
    elif not disk.volumes[0].writable:
        reasons.append("The exFAT volume is read-only or inaccessible.")
    return not reasons, tuple(reasons)


def verify_same_identity(selected: PhysicalDisk, current: PhysicalDisk) -> None:
    if selected.number != current.number or selected.identity_tuple() != current.identity_tuple():
        raise RuntimeError(
            f"{selected.physical_name} no longer matches the selected hardware identity. Operation aborted."
        )
