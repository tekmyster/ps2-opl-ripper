from __future__ import annotations

import logging
import os
import shutil
import tempfile
import time
import uuid
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import ValidationError
from ps2ripper.core.models import (
    DiscIdentity,
    MediaType,
    OpticalDrive,
    ProgressSnapshot,
    TrackKind,
)
from ps2ripper.imaging.ripper import (
    ProgressHandler,
    convert_cd_data_track_to_iso,
    rip_cd_bin_cue,
    rip_dvd_iso,
)
from ps2ripper.imaging.verification import copy_and_verify, sha256_file, validate_ps2_iso
from ps2ripper.opl.layout import OPLDrive
from ps2ripper.ps2.naming import opl_iso_filename
from ps2ripper.windows.optical_api import NativeOpticalDevice, OpticalBlockStream

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RipSettings:
    temporary_directory: Path
    read_chunk_sectors: int = 32
    maximum_retries: int = 8
    retain_temporary_image: bool = False
    retain_archival_bin_cue: bool = False


@dataclass(frozen=True)
class InstallResult:
    destination: Path | None
    source_sha256: str
    destination_sha256: str | None
    source_size: int
    elapsed_seconds: float
    retries: int
    archive_bin: Path | None = None
    archive_cue: Path | None = None


def _find_ps2_cd_track(device: NativeOpticalDevice, disc: DiscIdentity) -> int:
    from io import BytesIO

    import pycdlib

    from ps2ripper.ps2.system_cnf import parse_system_cnf

    for track in disc.tracks:
        if track.kind is TrackKind.AUDIO:
            continue
        stream = OpticalBlockStream(device, 0, track)
        iso = pycdlib.PyCdlib()
        try:
            iso.open_fp(stream)
            target = BytesIO()
            iso.get_file_from_iso_fp(target, iso_path="/SYSTEM.CNF;1")
            if parse_system_cnf(target.getvalue()).game_id == disc.game_id:
                return track.number
        except (pycdlib.pycdlibexception.PyCdlibException, ValidationError):
            pass
        finally:
            with suppress(pycdlib.pycdlibexception.PyCdlibException):
                iso.close()
    raise ValidationError("No CD data track contains the expected PS2 SYSTEM.CNF.")


def rip_and_install(
    optical_drive: OpticalDrive,
    disc: DiscIdentity,
    title: str,
    opl_root: Path,
    settings: RipSettings,
    token: CancellationToken,
    progress: ProgressHandler | None = None,
    replace_existing: bool = False,
    archive_only: bool = False,
    force_retain_archive: bool = False,
) -> InstallResult:
    started = time.monotonic()
    name = opl_iso_filename(disc.game_id, title)
    destination = OPLDrive(opl_root).destination_for_game(disc.media_type, disc.game_id, title)
    if destination.exists() and not replace_existing and not archive_only:
        raise FileExistsError(destination)
    settings.temporary_directory.mkdir(parents=True, exist_ok=True)
    task_directory = Path(
        tempfile.mkdtemp(prefix=f"PS2OPLRipper-{disc.game_id}-", dir=settings.temporary_directory)
    )
    source_image: Path | None = None
    archive_bin: Path | None = None
    archive_cue: Path | None = None
    image_result = None
    try:
        with NativeOpticalDevice(optical_drive) as device:
            from ps2ripper.optical.media_detector import inspect_disc

            current = inspect_disc(device)
            if current.game_id != disc.game_id or current.media_type != disc.media_type:
                raise ValidationError(
                    "The disc changed after it was inspected. Ripping was aborted."
                )
            if disc.media_type in (MediaType.PS2_DVD5, MediaType.PS2_DVD9):
                source_image = task_directory / name
                image_result = rip_dvd_iso(
                    device,
                    source_image,
                    disc.total_sectors,
                    token,
                    progress,
                    settings.read_chunk_sectors,
                    settings.maximum_retries,
                )
            elif disc.media_type is MediaType.PS2_CD:
                stem = name.removesuffix(".iso")
                bin_path = task_directory / f"{stem}.bin"
                cue_path = task_directory / f"{stem}.cue"
                raw_result = rip_cd_bin_cue(
                    device,
                    bin_path,
                    cue_path,
                    disc.tracks,
                    token,
                    progress,
                    max(1, settings.read_chunk_sectors // 2),
                    settings.maximum_retries,
                )
                track_number = _find_ps2_cd_track(device, disc)
                if archive_only:
                    image_result = raw_result
                else:
                    source_image = task_directory / name
                    image_result = convert_cd_data_track_to_iso(
                        bin_path,
                        source_image,
                        disc.tracks,
                        track_number,
                        token,
                        progress,
                    )
                retain_archive = (
                    settings.retain_archival_bin_cue or force_retain_archive or archive_only
                )
                if retain_archive:
                    archive_directory = (
                        settings.temporary_directory / "PS2 OPL Ripper Archives" / stem
                    )
                    archive_directory.mkdir(parents=True, exist_ok=True)
                    archive_bin = archive_directory / bin_path.name
                    archive_cue = archive_directory / cue_path.name
                    if archive_bin.exists() or archive_cue.exists():
                        raise FileExistsError(archive_bin if archive_bin.exists() else archive_cue)
                    shutil.move(bin_path, archive_bin)
                    shutil.move(cue_path, archive_cue)
                if archive_only:
                    return InstallResult(
                        None,
                        raw_result.sha256,
                        None,
                        raw_result.size,
                        time.monotonic() - started,
                        raw_result.retries,
                        archive_bin,
                        archive_cue,
                    )
            else:
                raise ValidationError("The selected media is not a recognized PS2 CD/DVD.")

        assert source_image is not None and image_result is not None
        if not image_result.complete:
            raise ValidationError(
                "The ripped image contains damaged sectors and will not be installed."
            )
        validate_ps2_iso(source_image, disc.game_id)
        OPLDrive(opl_root).verify_free_space(image_result.size)
        partial = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.partial")
        try:
            destination_hash = copy_and_verify(
                source_image,
                partial,
                image_result.sha256,
                token,
                (
                    lambda done, total: progress(
                        ProgressSnapshot("Copying and verifying", done, total)
                    )
                )
                if progress
                else None,
            )
            validate_ps2_iso(partial, disc.game_id)
            if destination.exists() and not replace_existing:
                raise FileExistsError(destination)
            os.replace(partial, destination)
        finally:
            partial.unlink(missing_ok=True)
        # The verified temporary destination was renamed on the same volume;
        # reread the final path so the logged B hash is explicitly final.
        final_hash = sha256_file(destination, token)
        if final_hash != image_result.sha256 or destination_hash != image_result.sha256:
            raise ValidationError("Final destination SHA-256 verification failed.")
        validate_ps2_iso(destination, disc.game_id)
        logger.info(
            "Installed %s as %s; size=%d sha256=%s retries=%d elapsed=%.1fs",
            disc.game_id,
            destination,
            image_result.size,
            final_hash,
            image_result.retries,
            time.monotonic() - started,
        )
        return InstallResult(
            destination,
            image_result.sha256,
            final_hash,
            image_result.size,
            time.monotonic() - started,
            image_result.retries,
            archive_bin,
            archive_cue,
        )
    finally:
        if settings.retain_temporary_image and source_image and source_image.exists():
            retained = (
                settings.temporary_directory
                / "PS2 OPL Ripper Retained Images"
                / source_image.name
            )
            retained.parent.mkdir(parents=True, exist_ok=True)
            if not retained.exists():
                shutil.move(source_image, retained)
        shutil.rmtree(task_directory, ignore_errors=True)
