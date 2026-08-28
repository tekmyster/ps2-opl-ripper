from __future__ import annotations

from pathlib import Path

from ps2ripper.core.models import CDTrack


def frames_to_msf(frames: int) -> str:
    if frames < 0:
        raise ValueError("CUE time cannot be negative")
    minutes, remainder = divmod(frames, 75 * 60)
    seconds, frame = divmod(remainder, 75)
    return f"{minutes:02d}:{seconds:02d}:{frame:02d}"


def generate_cue(bin_filename: str, tracks: tuple[CDTrack, ...]) -> str:
    if not tracks:
        raise ValueError("At least one track is required")
    safe_name = Path(bin_filename).name.replace('"', "'")
    lines = [f'FILE "{safe_name}" BINARY']
    for track in tracks:
        lines.append(f"  TRACK {track.number:02d} {track.kind.value}")
        if track.pregap_frames:
            lines.append(f"    PREGAP {frames_to_msf(track.pregap_frames)}")
        lines.append(f"    INDEX 01 {frames_to_msf(track.file_index_lba)}")
    return "\r\n".join(lines) + "\r\n"
