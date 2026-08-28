from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes
from dataclasses import dataclass

from ps2ripper.core.exceptions import NativeCallError, OpticalReadError
from ps2ripper.core.models import CDTrack, OpticalDrive, TrackKind
from ps2ripper.imaging.cd_sector import SectorForm, identify_sector_form

from .native import (
    FILE_SHARE_READ,
    FILE_SHARE_WRITE,
    GENERIC_READ,
    GUID_DEVINTERFACE_CDROM,
    IOCTL_DVD_READ_STRUCTURE,
    IOCTL_SCSI_PASS_THROUGH_DIRECT,
    IOCTL_STORAGE_EJECT_MEDIA,
    IOCTL_STORAGE_GET_DEVICE_NUMBER,
    IOCTL_STORAGE_QUERY_PROPERTY,
    SCSI_PASS_THROUGH_DIRECT,
    SPDRP_DEVICEDESC,
    SPDRP_FRIENDLYNAME,
    SPTD_WITH_SENSE,
    STORAGE_PROPERTY_QUERY,
    WinHandle,
    device_io_control,
    kernel32,
    raise_last_error,
)
from .setup_devices import enumerate_device_interfaces

DRIVE_CDROM = 5
SCSI_IOCTL_DATA_IN = 1


@dataclass(frozen=True)
class SenseData:
    key: int
    asc: int
    ascq: int
    raw: bytes

    @property
    def description(self) -> str:
        return f"sense key 0x{self.key:02X}, ASC/ASCQ 0x{self.asc:02X}/0x{self.ascq:02X}"


class SCSICommandError(OSError):
    def __init__(self, opcode: int, status: int, sense: SenseData) -> None:
        self.opcode = opcode
        self.status = status
        self.sense = sense
        super().__init__(
            f"SCSI command 0x{opcode:02X} failed with status 0x{status:02X} ({sense.description})"
        )


def _storage_device_number(handle: WinHandle) -> int:
    raw = device_io_control(
        handle, IOCTL_STORAGE_GET_DEVICE_NUMBER, out_size=12, operation="Optical device number"
    )
    return struct.unpack_from("<I", raw, 4)[0]


def _drive_letters_by_device_number() -> dict[int, str]:
    result: dict[int, str] = {}
    mask = kernel32.GetLogicalDrives()
    for index in range(26):
        if not mask & (1 << index):
            continue
        letter = f"{chr(65 + index)}:"
        if kernel32.GetDriveTypeW(f"{letter}\\") != DRIVE_CDROM:
            continue
        try:
            with WinHandle.open(rf"\\.\{letter}") as handle:
                result[_storage_device_number(handle)] = letter
        except OSError:
            continue
    return result


def enumerate_optical_drives() -> tuple[OpticalDrive, ...]:
    letters = _drive_letters_by_device_number()
    interfaces = enumerate_device_interfaces(
        GUID_DEVINTERFACE_CDROM, (SPDRP_FRIENDLYNAME, SPDRP_DEVICEDESC)
    )
    drives: list[OpticalDrive] = []
    for interface in interfaces:
        try:
            with WinHandle.open(interface.path) as handle:
                number = _storage_device_number(handle)
        except OSError:
            continue
        description = interface.properties.get(SPDRP_FRIENDLYNAME, "") or interface.properties.get(
            SPDRP_DEVICEDESC, "Optical drive"
        )
        drive = OpticalDrive(
            device_path=interface.path,
            drive_letter=letters.get(number),
            vendor="",
            product=description,
            instance_id=interface.instance_id,
        )
        try:
            with NativeOpticalDevice(drive) as device:
                vendor, product, revision = device.inquiry()
            drive = OpticalDrive(
                drive.device_path,
                drive.drive_letter,
                vendor,
                product or description,
                revision,
                drive.instance_id,
            )
        except OSError:
            pass
        drives.append(drive)
    return tuple(drives)


def _parse_sense(raw: bytes) -> SenseData:
    if len(raw) >= 14 and raw[0] & 0x7F in (0x70, 0x71):
        return SenseData(raw[2] & 0x0F, raw[12], raw[13], raw)
    if len(raw) >= 4 and raw[0] & 0x7F in (0x72, 0x73):
        return SenseData(raw[1] & 0x0F, raw[2], raw[3], raw)
    return SenseData(0, 0, 0, raw)


class NativeOpticalDevice:
    def __init__(self, drive: OpticalDrive) -> None:
        self.drive = drive
        path = rf"\\.\{drive.drive_letter}" if drive.drive_letter else drive.device_path
        self.handle = WinHandle.open(path, GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE)
        self.alignment_mask = self._query_alignment_mask()

    def close(self) -> None:
        self.handle.close()

    def __enter__(self) -> NativeOpticalDevice:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _query_alignment_mask(self) -> int:
        query = STORAGE_PROPERTY_QUERY(PropertyId=1, QueryType=0)
        try:
            raw = device_io_control(
                self.handle, IOCTL_STORAGE_QUERY_PROPERTY, query, 64, "StorageAdapterProperty"
            )
            return struct.unpack_from("<I", raw, 16)[0] if len(raw) >= 20 else 0
        except OSError:
            return 0

    def send_cdb(self, cdb: bytes, data_length: int = 0, timeout: int = 30) -> bytes:
        if not 1 <= len(cdb) <= 16:
            raise ValueError("CDB must contain 1 to 16 bytes")
        packet = SPTD_WITH_SENSE()
        packet.sptd.Length = ctypes.sizeof(SCSI_PASS_THROUGH_DIRECT)
        packet.sptd.CdbLength = len(cdb)
        packet.sptd.SenseInfoLength = len(packet.sense)
        packet.sptd.DataIn = SCSI_IOCTL_DATA_IN
        packet.sptd.DataTransferLength = data_length
        packet.sptd.TimeOutValue = timeout
        packet.sptd.SenseInfoOffset = SPTD_WITH_SENSE.sense.offset
        for index, value in enumerate(cdb):
            packet.sptd.Cdb[index] = value

        base = (
            ctypes.create_string_buffer(data_length + self.alignment_mask + 1)
            if data_length
            else None
        )
        if base is not None:
            address = (ctypes.addressof(base) + self.alignment_mask) & ~self.alignment_mask
            packet.sptd.DataBuffer = address
        returned = wintypes.DWORD()
        ok = kernel32.DeviceIoControl(
            self.handle.value,
            IOCTL_SCSI_PASS_THROUGH_DIRECT,
            ctypes.byref(packet),
            ctypes.sizeof(packet),
            ctypes.byref(packet),
            ctypes.sizeof(packet),
            ctypes.byref(returned),
            None,
        )
        if not ok:
            raise_last_error(f"SPTI command 0x{cdb[0]:02X}")
        if packet.sptd.ScsiStatus:
            raise SCSICommandError(
                cdb[0], packet.sptd.ScsiStatus, _parse_sense(bytes(packet.sense))
            )
        transferred = min(packet.sptd.DataTransferLength, data_length)
        return ctypes.string_at(packet.sptd.DataBuffer, transferred) if transferred else b""

    def test_unit_ready(self) -> bool:
        try:
            self.send_cdb(b"\x00\0\0\0\0\0")
            return True
        except (SCSICommandError, NativeCallError):
            return False

    def inquiry(self) -> tuple[str, str, str]:
        data = self.send_cdb(bytes((0x12, 0, 0, 0, 96, 0)), 96)
        return (
            data[8:16].decode("ascii", "replace").strip(),
            data[16:32].decode("ascii", "replace").strip(),
            data[32:36].decode("ascii", "replace").strip(),
        )

    def current_profile(self) -> int:
        cdb = bytearray(10)
        cdb[0] = 0x46
        cdb[1] = 0x02
        cdb[7:9] = (8).to_bytes(2, "big")
        data = self.send_cdb(bytes(cdb), 8)
        if len(data) < 8:
            raise OSError("GET CONFIGURATION response was truncated")
        return int.from_bytes(data[6:8], "big")

    def read_capacity(self) -> tuple[int, int]:
        data = self.send_cdb(bytes((0x25, 0, 0, 0, 0, 0, 0, 0, 0, 0)), 8)
        if len(data) != 8:
            raise OSError("READ CAPACITY response was truncated")
        return int.from_bytes(data[:4], "big") + 1, int.from_bytes(data[4:], "big")

    def read_dvd_layer_count(self) -> int | None:
        request = struct.pack("<qIIB", 0, 0, 0, 0)
        try:
            data = device_io_control(
                self.handle,
                IOCTL_DVD_READ_STRUCTURE,
                request,
                256,
                "IOCTL_DVD_READ_STRUCTURE",
            )
        except OSError:
            return None
        if len(data) < 21:
            return None
        descriptor = data[4:21]
        return ((descriptor[2] >> 5) & 0x03) + 1

    def read_blocks(self, lba: int, count: int, sector_size: int = 2048) -> bytes:
        if not 0 <= lba <= 0xFFFFFFFF or not 1 <= count <= 0xFFFFFFFF:
            raise ValueError("READ(12) range is invalid")
        cdb = bytearray(12)
        cdb[0] = 0xA8
        cdb[2:6] = lba.to_bytes(4, "big")
        cdb[6:10] = count.to_bytes(4, "big")
        data = self.send_cdb(bytes(cdb), count * sector_size, max(30, count * 2))
        if len(data) != count * sector_size:
            raise OpticalReadError(lba, 1, "The drive returned a short read.")
        return data

    def read_toc(self) -> tuple[CDTrack, ...]:
        if self.read_session_count() != 1:
            from ps2ripper.core.exceptions import ValidationError

            raise ValidationError("Multi-session CDs are not supported by this release.")
        cdb = bytearray(10)
        cdb[0] = 0x43
        cdb[7:9] = (804).to_bytes(2, "big")
        data = self.send_cdb(bytes(cdb), 804)
        if len(data) < 4:
            raise OSError("READ TOC response was truncated")
        total = min(int.from_bytes(data[:2], "big") + 2, len(data))
        entries: list[tuple[int, bool, int]] = []
        for offset in range(4, total - 7, 8):
            control = data[offset + 1] & 0x0F
            number = data[offset + 2]
            lba = int.from_bytes(data[offset + 4 : offset + 8], "big")
            entries.append((number, bool(control & 0x04), lba))
        leadout = next((lba for number, _data, lba in entries if number == 0xAA), None)
        tracks = [(number, is_data, lba) for number, is_data, lba in entries if number != 0xAA]
        if not tracks or leadout is None:
            raise OSError("TOC did not contain tracks and a lead-out address")
        result: list[CDTrack] = []
        base_lba = tracks[0][2]
        for index, (number, is_data, start) in enumerate(tracks):
            end = (tracks[index + 1][2] if index + 1 < len(tracks) else leadout) - 1
            if is_data:
                raw = self.read_cd_raw_any(start, 1)
                form = identify_sector_form(raw)
                kind = TrackKind.MODE1_2352 if form is SectorForm.MODE1 else TrackKind.MODE2_2352
            else:
                kind = TrackKind.AUDIO
            result.append(CDTrack(number, kind, start, end, start - base_lba))
        return tuple(result)

    def read_session_count(self) -> int:
        cdb = bytearray(10)
        cdb[0] = 0x43
        cdb[2] = 0x01
        cdb[7:9] = (12).to_bytes(2, "big")
        data = self.send_cdb(bytes(cdb), 12)
        if len(data) < 4:
            raise OSError("Session information response was truncated")
        first_session, last_session = data[2], data[3]
        if not first_session or last_session < first_session:
            raise OSError("Session information was invalid")
        return last_session - first_session + 1

    def read_cd_raw_any(self, lba: int, count: int) -> bytes:
        cdb = bytearray(12)
        cdb[0] = 0xBE
        cdb[2:6] = lba.to_bytes(4, "big")
        cdb[6:9] = count.to_bytes(3, "big")
        cdb[9] = 0xF8
        return self.send_cdb(bytes(cdb), count * 2352, max(30, count * 2))

    def read_cd_raw(self, lba: int, count: int, kind: TrackKind) -> bytes:
        cdb = bytearray(12)
        cdb[0] = 0xBE
        expected = {
            TrackKind.AUDIO: 1,
            TrackKind.MODE1_2352: 2,
            TrackKind.MODE2_2352: 3,
        }[kind]
        cdb[1] = expected << 2
        cdb[2:6] = lba.to_bytes(4, "big")
        cdb[6:9] = count.to_bytes(3, "big")
        cdb[9] = 0x10 if kind is TrackKind.AUDIO else 0xF8
        data = self.send_cdb(bytes(cdb), count * 2352, max(30, count * 2))
        if len(data) != count * 2352:
            raise OpticalReadError(lba, 1, "The drive returned a short raw-CD read.")
        return data

    def eject(self) -> None:
        device_io_control(self.handle, IOCTL_STORAGE_EJECT_MEDIA, operation="Eject optical media")


class OpticalBlockStream:
    """Seekable 2048-byte view used by pycdlib without loading the image."""

    def __init__(
        self,
        device: NativeOpticalDevice,
        sectors: int,
        data_track: CDTrack | None = None,
    ) -> None:
        self.device = device
        self.sectors = (
            sectors if data_track is None else data_track.end_lba - data_track.start_lba + 1
        )
        self.data_track = data_track
        self.position = 0

    def seek(self, offset: int, whence: int = 0) -> int:
        target = (
            offset
            if whence == 0
            else self.position + offset
            if whence == 1
            else self.sectors * 2048 + offset
        )
        if target < 0:
            raise ValueError("negative seek")
        self.position = min(target, self.sectors * 2048)
        return self.position

    def tell(self) -> int:
        return self.position

    def read(self, size: int = -1) -> bytes:
        remaining = self.sectors * 2048 - self.position
        if size < 0 or size > remaining:
            size = remaining
        if not size:
            return b""
        first_sector, intra = divmod(self.position, 2048)
        count = (intra + size + 2047) // 2048
        if self.data_track is None:
            data = self.device.read_blocks(first_sector, count)
        else:
            from ps2ripper.imaging.cd_sector import extract_2048_user_data

            raw = self.device.read_cd_raw(
                self.data_track.start_lba + first_sector, count, self.data_track.kind
            )
            data = b"".join(
                extract_2048_user_data(raw[offset : offset + 2352])
                for offset in range(0, len(raw), 2352)
            )
        result = data[intra : intra + size]
        self.position += len(result)
        return result

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True
