from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path


class PartitionStyle(Enum):
    RAW = auto()
    MBR = auto()
    GPT = auto()
    UNKNOWN = auto()


class MediaType(Enum):
    NO_MEDIA = auto()
    PS2_CD = auto()
    PS2_DVD5 = auto()
    PS2_DVD9 = auto()
    AUDIO_CD = auto()
    DVD_VIDEO = auto()
    UNSUPPORTED_DATA = auto()
    UNREADABLE = auto()
    UNKNOWN = auto()


class TrackKind(Enum):
    MODE1_2352 = "MODE1/2352"
    MODE2_2352 = "MODE2/2352"
    AUDIO = "AUDIO"


@dataclass(frozen=True)
class VolumeInfo:
    guid_path: str
    mount_points: tuple[str, ...] = ()
    filesystem: str | None = None
    label: str | None = None
    writable: bool = False
    disk_numbers: tuple[int, ...] = ()


@dataclass(frozen=True)
class PartitionInfo:
    number: int
    offset: int
    length: int
    style: PartitionStyle
    type_description: str = ""
    is_boot: bool = False
    is_system: bool = False
    is_recovery: bool = False
    is_efi: bool = False


@dataclass(frozen=True)
class PhysicalDisk:
    number: int
    device_path: str
    instance_id: str
    model: str
    manufacturer: str = ""
    serial: str = ""
    bus_type: str = "Unknown"
    capacity: int = 0
    logical_sector_size: int = 512
    removable: bool = False
    usb: bool = False
    partition_style: PartitionStyle = PartitionStyle.UNKNOWN
    partitions: tuple[PartitionInfo, ...] = ()
    volumes: tuple[VolumeInfo, ...] = ()
    safety_reasons: tuple[str, ...] = ()

    @property
    def physical_name(self) -> str:
        return f"PhysicalDrive{self.number}"

    @property
    def destructive_access_allowed(self) -> bool:
        return self.usb and not self.safety_reasons

    def identity_tuple(self) -> tuple[object, ...]:
        return (
            self.instance_id,
            self.serial,
            self.model,
            self.capacity,
            self.logical_sector_size,
            self.usb,
        )


@dataclass(frozen=True)
class OpticalDrive:
    device_path: str
    drive_letter: str | None
    vendor: str
    product: str
    revision: str = ""
    instance_id: str = ""

    @property
    def display_name(self) -> str:
        model = " ".join(part for part in (self.vendor, self.product) if part).strip()
        return f"{model or 'Optical drive'} — {self.drive_letter or self.device_path}"


@dataclass(frozen=True)
class CDTrack:
    number: int
    kind: TrackKind
    start_lba: int
    end_lba: int
    file_index_lba: int
    pregap_frames: int = 0

    def __post_init__(self) -> None:
        if self.number < 1 or self.end_lba < self.start_lba:
            raise ValueError("Invalid CD track range")


@dataclass(frozen=True)
class DiscIdentity:
    game_id: str
    media_type: MediaType
    title: str = ""
    total_sectors: int = 0
    sector_size: int = 2048
    tracks: tuple[CDTrack, ...] = ()


@dataclass(frozen=True)
class ImageResult:
    path: Path
    size: int
    sha256: str
    damaged_lbas: tuple[int, ...] = ()
    retries: int = 0

    @property
    def complete(self) -> bool:
        return not self.damaged_lbas


@dataclass
class ProgressSnapshot:
    operation: str
    completed_bytes: int
    total_bytes: int
    current_lba: int | None = None
    retries: int = 0
    elapsed_seconds: float = 0.0
    current_bytes_per_second: float = 0.0
    average_bytes_per_second: float = 0.0
    details: dict[str, str] = field(default_factory=dict)

    @property
    def fraction(self) -> float:
        return self.completed_bytes / self.total_bytes if self.total_bytes else 0.0
