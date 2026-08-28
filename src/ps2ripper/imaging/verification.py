from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path

import pycdlib

from ps2ripper.core.cancellation import CancellationToken
from ps2ripper.core.exceptions import ValidationError
from ps2ripper.ps2.system_cnf import parse_system_cnf

ProgressCallback = Callable[[int, int], None]


def sha256_file(
    path: Path,
    token: CancellationToken | None = None,
    progress: ProgressCallback | None = None,
    chunk_size: int = 4 * 1024 * 1024,
) -> str:
    digest = hashlib.sha256()
    completed = 0
    total = path.stat().st_size
    with path.open("rb", buffering=0) as source:
        while chunk := source.read(chunk_size):
            if token:
                token.checkpoint()
            digest.update(chunk)
            completed += len(chunk)
            if progress:
                progress(completed, total)
    return digest.hexdigest()


def copy_and_verify(
    source: Path,
    destination: Path,
    expected_sha256: str,
    token: CancellationToken | None = None,
    progress: ProgressCallback | None = None,
    chunk_size: int = 4 * 1024 * 1024,
) -> str:
    if destination.exists():
        raise FileExistsError(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    completed = 0
    total = source.stat().st_size
    try:
        with source.open("rb", buffering=0) as src, destination.open("xb", buffering=0) as dst:
            while chunk := src.read(chunk_size):
                if token:
                    token.checkpoint()
                dst.write(chunk)
                completed += len(chunk)
                if progress:
                    progress(completed, total)
            dst.flush()
            os.fsync(dst.fileno())
        actual = sha256_file(destination, token)
        if actual.lower() != expected_sha256.lower():
            raise ValidationError("Destination SHA-256 does not match the ripped image.")
        return actual
    except BaseException:
        if destination.exists():
            destination.unlink()
        raise


def validate_ps2_iso(path: Path, expected_game_id: str | None = None) -> str:
    if path.stat().st_size < 16 * 2048:
        raise ValidationError("ISO image is too small to contain an ISO9660 filesystem.")
    iso = pycdlib.PyCdlib()
    try:
        iso.open(str(path))
        record = iso.get_record(iso_path="/SYSTEM.CNF;1")
        if record is None:
            raise ValidationError("ISO does not contain SYSTEM.CNF.")
        from io import BytesIO

        target = BytesIO()
        iso.get_file_from_iso_fp(target, iso_path="/SYSTEM.CNF;1")
        game_id = parse_system_cnf(target.getvalue()).game_id
        if expected_game_id and game_id != expected_game_id:
            raise ValidationError(
                f"ISO game ID {game_id} does not match expected ID {expected_game_id}."
            )
        return game_id
    except pycdlib.pycdlibexception.PyCdlibException as exc:
        raise ValidationError(f"ISO9660 validation failed: {exc}") from exc
    finally:
        with suppress(pycdlib.pycdlibexception.PyCdlibException):
            iso.close()
