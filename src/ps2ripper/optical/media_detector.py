from __future__ import annotations

from contextlib import suppress
from io import BytesIO

import pycdlib

from ps2ripper.core.exceptions import ValidationError
from ps2ripper.core.models import DiscIdentity, MediaType, TrackKind
from ps2ripper.ps2.system_cnf import parse_system_cnf
from ps2ripper.windows.optical_api import NativeOpticalDevice, OpticalBlockStream

CD_PROFILES = {0x0008, 0x0009, 0x000A}
DVD_PROFILES = {
    0x0010,
    0x0011,
    0x0012,
    0x0013,
    0x0014,
    0x0015,
    0x0016,
    0x0017,
    0x0018,
    0x001A,
    0x001B,
    0x002A,
    0x002B,
}


def _game_id_from_stream(stream: OpticalBlockStream) -> str:
    iso = pycdlib.PyCdlib()
    try:
        iso.open_fp(stream)
        target = BytesIO()
        iso.get_file_from_iso_fp(target, iso_path="/SYSTEM.CNF;1")
        return parse_system_cnf(target.getvalue()).game_id
    except (pycdlib.pycdlibexception.PyCdlibException, ValidationError) as exc:
        raise ValidationError(
            "This disc does not appear to contain a recognizable PS2 SYSTEM.CNF."
        ) from exc
    finally:
        with suppress(pycdlib.pycdlibexception.PyCdlibException):
            iso.close()


def _is_dvd_video(stream: OpticalBlockStream) -> bool:
    iso = pycdlib.PyCdlib()
    try:
        stream.seek(0)
        iso.open_fp(stream)
        return iso.get_record(iso_path="/VIDEO_TS") is not None
    except pycdlib.pycdlibexception.PyCdlibException:
        return False
    finally:
        with suppress(pycdlib.pycdlibexception.PyCdlibException):
            iso.close()


def inspect_disc(device: NativeOpticalDevice) -> DiscIdentity:
    if not device.test_unit_ready():
        return DiscIdentity("", MediaType.NO_MEDIA)
    profile = device.current_profile()
    if profile in DVD_PROFILES:
        sectors, sector_size = device.read_capacity()
        if sector_size != 2048:
            return DiscIdentity(
                "", MediaType.UNKNOWN, total_sectors=sectors, sector_size=sector_size
            )
        layers = device.read_dvd_layer_count()
        media = (
            MediaType.PS2_DVD9
            if (layers and layers > 1) or sectors * sector_size > 5_000_000_000
            else MediaType.PS2_DVD5
        )
        stream = OpticalBlockStream(device, sectors)
        try:
            game_id = _game_id_from_stream(stream)
        except ValidationError:
            if _is_dvd_video(stream):
                return DiscIdentity("", MediaType.DVD_VIDEO, total_sectors=sectors)
            stream.seek(16 * 2048)
            signature = stream.read(6)
            if signature[1:6] == b"CD001":
                return DiscIdentity("", MediaType.UNSUPPORTED_DATA, total_sectors=sectors)
            return DiscIdentity("", MediaType.DVD_VIDEO, total_sectors=sectors)
        return DiscIdentity(game_id, media, total_sectors=sectors)
    if profile in CD_PROFILES:
        tracks = device.read_toc()
        data_tracks = [track for track in tracks if track.kind is not TrackKind.AUDIO]
        if not data_tracks:
            return DiscIdentity("", MediaType.AUDIO_CD, tracks=tracks)
        for track in data_tracks:
            stream = OpticalBlockStream(device, 0, track)
            try:
                game_id = _game_id_from_stream(stream)
                return DiscIdentity(
                    game_id,
                    MediaType.PS2_CD,
                    total_sectors=track.end_lba - track.start_lba + 1,
                    tracks=tracks,
                )
            except ValidationError:
                continue
        return DiscIdentity("", MediaType.UNSUPPORTED_DATA, tracks=tracks)
    return DiscIdentity("", MediaType.UNKNOWN)
