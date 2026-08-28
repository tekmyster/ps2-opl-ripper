from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from FATtools import Volume, disk, mkfat, partutils, vhdutils
from ps2ripper.core.exceptions import ValidationError
from ps2ripper.opl.layout import OPL_DIRECTORIES

SECTOR_SIZE = 512
MIB = 1024 * 1024


class DiskStream(Protocol):
    size: int
    mode: str

    def type(self) -> str: ...
    def seek(self, offset: int, whence: int = 0) -> None: ...
    def tell(self) -> int: ...
    def read(self, size: int) -> bytes | bytearray: ...
    def write(self, data: bytes | bytearray | memoryview) -> None: ...
    def flush(self) -> None: ...
    def close(self) -> None: ...


class _NonClosingStream:
    """Shield the caller-owned stream from FATtools' phase-boundary close()."""

    def __init__(self, stream: DiskStream) -> None:
        self._stream = stream
        self.size = stream.size
        self.mode = stream.mode

    def __getattr__(self, name: str):
        return getattr(self._stream, name)

    def type(self) -> str:
        return self._stream.type()

    def seek(self, offset: int, whence: int = 0) -> None:
        self._stream.seek(offset, whence)

    def tell(self) -> int:
        return self._stream.tell()

    def read(self, size: int) -> bytes | bytearray:
        return self._stream.read(size)

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self._stream.write(data)

    def flush(self) -> None:
        self._stream.flush()

    def close(self) -> None:
        self._stream.flush()


@dataclass(frozen=True)
class FormatResult:
    partition_offset: int
    partition_size: int
    cluster_size: int
    directories: tuple[str, ...]


def recommended_exfat_cluster_size(partition_size: int) -> int:
    # Windows' documented/default format behavior for exFAT capacity ranges.
    if partition_size <= 256 * MIB:
        return 4 * 1024
    if partition_size <= 32 * 1024**3:
        return 32 * 1024
    return 128 * 1024


def _format_stream(raw: DiskStream) -> FormatResult:
    if raw.size < 64 * MIB:
        raise ValidationError("The disk is too small for the supported OPL exFAT layout.")
    if raw.size > 0xFFFFFFFF * SECTOR_SIZE:
        raise ValidationError("The disk exceeds the supported MBR address range.")
    protected = _NonClosingStream(raw)
    mbr = partutils.partition(
        protected,
        "mbr",
        {
            "phys_sector": SECTOR_SIZE,
            "lba_mode": 1,
            "mbr_type": 0x07,
        },
    )
    entry = mbr.partitions[0]
    partition_offset = entry.dwFirstSectorLBA * SECTOR_SIZE
    partition_size = entry.dwTotalSectors * SECTOR_SIZE
    cluster_size = recommended_exfat_cluster_size(partition_size)
    protected.seek(0)
    partition = disk.partition(protected, partition_offset, partition_size)
    partition.mbr = mbr
    result = mkfat.exfat_mkfs(
        partition,
        partition.size,
        SECTOR_SIZE,
        {"wanted_cluster": cluster_size},
    )
    if result != 0:
        raise ValidationError(f"FATtools exFAT formatter failed with status {result}.")
    partition.flush()

    root = Volume.openvolume(partition)
    if root == "EINV":
        raise ValidationError("FATtools could not reopen the new exFAT filesystem.")
    try:
        for name in OPL_DIRECTORIES:
            if not root.opendir(name):
                created = root.mkdir(name)
                if created is None:
                    raise ValidationError(f"Unable to create OPL directory {name}.")
        root.flush()
    finally:
        root.close()
        partition.flush()
        protected.flush()
    return FormatResult(partition_offset, partition_size, cluster_size, OPL_DIRECTORIES)


def initialize_image(path: Path, size: int) -> FormatResult:
    if path.exists():
        raise FileExistsError(path)
    with path.open("xb") as image:
        image.truncate(size)
    raw = disk.disk(str(path), "r+b")
    try:
        return _format_stream(raw)
    finally:
        raw.close()


def initialize_vhd(path: Path, size: int) -> FormatResult:
    """Create and format a disposable dynamic VHD for Windows mount tests."""
    if path.exists():
        raise FileExistsError(path)
    vhdutils.mk_dynamic(str(path), size)
    raw = vhdutils.Image(str(path), "r+b")
    try:
        return _format_stream(raw)
    finally:
        raw.close()


def initialize_stream(raw: DiskStream) -> FormatResult:
    """Format an already identity-verified, exclusively locked raw disk stream."""
    return _format_stream(raw)


def independently_check_boot_regions(path: Path, expected: FormatResult) -> None:
    with path.open("rb") as image:
        mbr = image.read(512)
        if mbr[510:512] != b"\x55\xaa":
            raise ValidationError("MBR signature is missing.")
        status = mbr[446]
        partition_type = mbr[450]
        start_lba, sectors = struct.unpack_from("<II", mbr, 454)
        if status != 0:
            raise ValidationError("OPL data partition was unexpectedly marked active.")
        if partition_type != 0x07:
            raise ValidationError(f"Unexpected MBR partition type 0x{partition_type:02X}.")
        if start_lba * 512 != expected.partition_offset or sectors * 512 != expected.partition_size:
            raise ValidationError("MBR partition range does not match the formatter result.")
        image.seek(expected.partition_offset)
        boot = image.read(512)
        if boot[3:11] != b"EXFAT   ":
            raise ValidationError("exFAT OEM signature is missing.")
        part_offset = struct.unpack_from("<Q", boot, 0x40)[0]
        if part_offset != start_lba:
            raise ValidationError(
                f"exFAT PartitionOffset is {part_offset} sectors; expected {start_lba}."
            )
        bytes_per_sector = 1 << boot[0x6C]
        sectors_per_cluster = 1 << boot[0x6D]
        if bytes_per_sector * sectors_per_cluster != expected.cluster_size:
            raise ValidationError("exFAT cluster size does not match the requested default.")


def reopen_image_directories(path: Path) -> tuple[str, ...]:
    root = Volume.vopen(str(path), "rb", "volume")
    if root == "EINV":
        raise ValidationError("FATtools could not reopen the image filesystem.")
    try:
        return tuple(name for name in OPL_DIRECTORIES if root.opendir(name))
    finally:
        Volume.vclose(root)
