from ps2ripper.core.models import CDTrack, TrackKind
from ps2ripper.imaging.cue_writer import frames_to_msf, generate_cue


def test_frames_to_msf():
    assert frames_to_msf(75 * 62 + 3) == "01:02:03"


def test_mixed_mode_cue():
    tracks = (
        CDTrack(1, TrackKind.MODE2_2352, 0, 999, 0),
        CDTrack(2, TrackKind.AUDIO, 1000, 1999, 1000, pregap_frames=150),
    )
    cue = generate_cue("Game.bin", tracks)
    assert 'FILE "Game.bin" BINARY' in cue
    assert "TRACK 01 MODE2/2352" in cue
    assert "TRACK 02 AUDIO" in cue
    assert "PREGAP 00:02:00" in cue
    assert "INDEX 01 00:13:25" in cue
