import json

import guitarpro as gp

from build_gp5 import build_week


def phrase(label: str, tempo: int, fret: int) -> dict:
    return {
        "label": label,
        "title": "Test",
        "tempo": tempo,
        "time_signature": [4, 4],
        "measures": [
            {"chord": "C",
             "beats": [{"duration": 1, "pick": "down",
                        "notes": [{"string": 6, "fret": fret,
                                   "techniques": ["hammer_on"]}]}]}
        ],
    }


def test_build_week_roundtrip(tmp_path):
    d = tmp_path / "json"
    d.mkdir()
    (d / "01_daily.json").write_text(
        json.dumps(phrase("Daily", 120, 8)), encoding="utf-8")
    (d / "02_monday.json").write_text(
        json.dumps(phrase("Monday", 100, 10)), encoding="utf-8")
    out = tmp_path / "week.gp5"

    build_week(str(d), str(out), "Test Week")
    song = gp.parse(str(out))

    measures = song.tracks[0].measures
    assert len(measures) == 2
    assert song.tempo == 120
    assert "Daily" in song.measureHeaders[0].marker.title
    assert "Monday" in song.measureHeaders[1].marker.title

    b0 = measures[0].voices[0].beats[0]
    assert (b0.notes[0].string, b0.notes[0].value) == (6, 8)
    assert b0.notes[0].effect.hammer is True
    assert b0.effect.pickStroke == gp.BeatStrokeDirection.down
    assert b0.text == "C"

    b1 = measures[1].voices[0].beats[0]
    assert b1.effect.mixTableChange.tempo.value == 100
    assert b1.notes[0].value == 10
