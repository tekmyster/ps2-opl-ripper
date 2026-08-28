from __future__ import annotations

import hashlib
import os
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import OpticalReadError, ValidationError
from ps2ripper.core.models import CDTrack, ImageResult, ProgressSnapshot, TrackKind
from ps2ripper.imaging.cd_sector import extract_2048_user_data
from ps2ripper.imaging.cue_writer import generate_cue

ProgressHandler = Callable[[ProgressSnapshot], None]


class DVDReader(Protocol):
    def read_blocks(self, lba: int, count: int, sector_size: int = 2048) -> bytes: ...


class CDReader(Protocol):
    def read_cd_raw(self, lba: int, count: int, kind: TrackKind) -> bytes: ...


def ensure_temporary_space(directory: Path, required_bytes: int) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    free = shutil.disk_usage(directory).free
    if free < required_bytes:
        raise ValidationError(
            f"Temporary storage needs {required_bytes:,} bytes but only {free:,} bytes are free."
        )


def _emit_progress(
    callback: ProgressHandler | None,
    operation: str,
    completed: int,
    total: int,
    current_lba: int,
    retries: int,
    started: float,
    window_started: float,
    window_bytes: int,
) -> tuple[float, int]:
    now = time.monotonic()
    elapsed = now - started
    window_elapsed = now - window_started
    if callback:
        callback(
            ProgressSnapshot(
                operation=operation,
                completed_bytes=completed,
                total_bytes=total,
                current_lba=current_lba,
                retries=retries,
                elapsed_seconds=elapsed,
                current_bytes_per_second=window_bytes / window_elapsed if window_elapsed else 0,
                average_bytes_per_second=completed / elapsed if elapsed else 0,
            )
        )
    return (now, 0) if window_elapsed >= 0.5 else (window_started, window_bytes)


def rip_dvd_iso(
    reader: DVDReader,
    destination: Path,
    total_sectors: int,
    token: CancellationToken,
    progress: ProgressHandler | None = None,
    chunk_sectors: int = 32,
    max_retries: int = 8,
    continue_damaged: bool = False,
) -> ImageResult:
    total_bytes = total_sectors * 2048
    ensure_temporary_space(destination.parent, total_bytes)
    if destination.exists():
        raise FileExistsError(destination)
    digest = hashlib.sha256()
    damaged: list[int] = []
    retries = 0
    lba = 0
    started = window_started = time.monotonic()
    window_bytes = 0
    try:
        with destination.open("xb", buffering=0) as output:
            while lba < total_sectors:
                token.checkpoint()
                desired = min(chunk_sectors, total_sectors - lba)
                attempt_size = desired
                attempts = 0
                while True:
                    try:
                        data = reader.read_blocks(lba, attempt_size)
                        break
                    except OSError as exc:
                        attempts += 1
                        retries += 1
                        if attempt_size > 1:
                            attempt_size = max(1, attempt_size // 2)
                            continue
                        if attempts <= max_retries:
                            continue
                        if not continue_damaged:
                            raise OpticalReadError(lba, attempts, str(exc)) from exc
                        data = bytes(2048)
                        damaged.append(lba)
                        break
                output.write(data)
                digest.update(data)
                lba += attempt_size
                window_bytes += len(data)
                window_started, window_bytes = _emit_progress(
                    progress,
                    "Ripping DVD",
                    lba * 2048,
                    total_bytes,
                    lba,
                    retries,
                    started,
                    window_started,
                    window_bytes,
                )
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return ImageResult(
        destination, destination.stat().st_size, digest.hexdigest(), tuple(damaged), retries
    )


def rip_cd_bin_cue(
    reader: CDReader,
    bin_path: Path,
    cue_path: Path,
    tracks: tuple[CDTrack, ...],
    token: CancellationToken,
    progress: ProgressHandler | None = None,
    chunk_sectors: int = 16,
    max_retries: int = 8,
) -> ImageResult:
    if not tracks:
        raise ValidationError("CD TOC contains no tracks.")
    first_lba = tracks[0].start_lba
    last_lba = tracks[-1].end_lba
    total_sectors = last_lba - first_lba + 1
    total_bytes = total_sectors * 2352
    ensure_temporary_space(bin_path.parent, total_bytes)
    if bin_path.exists() or cue_path.exists():
        raise FileExistsError(bin_path if bin_path.exists() else cue_path)
    digest = hashlib.sha256()
    retries = 0
    completed_sectors = 0
    started = window_started = time.monotonic()
    window_bytes = 0
    adjusted_tracks = tuple(
        CDTrack(
            track.number,
            track.kind,
            track.start_lba,
            track.end_lba,
            track.start_lba - first_lba,
            track.pregap_frames,
        )
        for track in tracks
    )
    try:
        with bin_path.open("xb", buffering=0) as output:
            for track in tracks:
                lba = track.start_lba
                while lba <= track.end_lba:
                    token.checkpoint()
                    count = min(chunk_sectors, track.end_lba - lba + 1)
                    attempt = 0
                    while True:
                        try:
                            data = reader.read_cd_raw(lba, count, track.kind)
                            break
                        except OSError as exc:
                            attempt += 1
                            retries += 1
                            if count > 1:
                                count = max(1, count // 2)
                            elif attempt > max_retries:
                                raise OpticalReadError(lba, attempt, str(exc)) from exc
                    output.write(data)
                    digest.update(data)
                    lba += count
                    completed_sectors += count
                    window_bytes += len(data)
                    window_started, window_bytes = _emit_progress(
                        progress,
                        "Archiving CD",
                        completed_sectors * 2352,
                        total_bytes,
                        lba,
                        retries,
                        started,
                        window_started,
                        window_bytes,
                    )
            output.flush()
            os.fsync(output.fileno())
        cue_path.write_text(
            generate_cue(bin_path.name, adjusted_tracks), encoding="utf-8", newline=""
        )
    except BaseException:
        bin_path.unlink(missing_ok=True)
        cue_path.unlink(missing_ok=True)
        raise
    return ImageResult(bin_path, bin_path.stat().st_size, digest.hexdigest(), retries=retries)


def convert_cd_data_track_to_iso(
    bin_path: Path,
    iso_path: Path,
    all_tracks: tuple[CDTrack, ...],
    data_track_number: int,
    token: CancellationToken,
    progress: ProgressHandler | None = None,
) -> ImageResult:
    track = next((item for item in all_tracks if item.number == data_track_number), None)
    if track is None or track.kind is TrackKind.AUDIO:
        raise ValidationError("The selected CD track is not a data track.")
    first_lba = all_tracks[0].start_lba
    start_frame = track.start_lba - first_lba
    sector_count = track.end_lba - track.start_lba + 1
    total_bytes = sector_count * 2048
    ensure_temporary_space(iso_path.parent, total_bytes)
    if iso_path.exists():
        raise FileExistsError(iso_path)
    digest = hashlib.sha256()
    started = time.monotonic()
    try:
        with bin_path.open("rb", buffering=0) as source, iso_path.open("xb", buffering=0) as output:
            source.seek(start_frame * 2352)
            for index in range(sector_count):
                token.checkpoint()
                raw = source.read(2352)
                if len(raw) != 2352:
                    raise ValidationError(f"Archival BIN ended at data-track sector {index}.")
                user_data = extract_2048_user_data(raw)
                output.write(user_data)
                digest.update(user_data)
                if progress and (index & 0xFF) == 0:
                    elapsed = time.monotonic() - started
                    completed = (index + 1) * 2048
                    progress(
                        ProgressSnapshot(
                            "Converting CD data track",
                            completed,
                            total_bytes,
                            track.start_lba + index,
                            elapsed_seconds=elapsed,
                            average_bytes_per_second=completed / elapsed if elapsed else 0,
                        )
                    )
            output.flush()
            os.fsync(output.fileno())
    except BaseException:
        iso_path.unlink(missing_ok=True)
        raise
    return ImageResult(iso_path, iso_path.stat().st_size, digest.hexdigest())
