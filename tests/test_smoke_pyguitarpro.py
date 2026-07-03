"""锁定 PyGuitarPro API 假设：写一个含全部所需特性的最小 song，写盘再读回逐项断言。"""
import guitarpro as gp


def test_roundtrip_minimal_song(tmp_path):
    song = gp.Song()
    song.title = "smoke"
    song.tempo = 120
    track = song.tracks[0]
    track.name = "Electric Guitar"
    track.channel.instrument = 30  # Distortion Guitar

    header = song.measureHeaders[0]
    header.timeSignature.numerator = 4
    header.timeSignature.denominator.value = 4
    header.marker = gp.Marker(title="Daily bpm=120")

    voice = track.measures[0].voices[0]
    beat = gp.Beat(voice)
    beat.status = gp.BeatStatus.normal
    beat.duration = gp.Duration(value=1)  # 全音符，填满 4/4
    beat.text = "C"
    beat.effect.pickStroke = gp.BeatStrokeDirection.down
    beat.effect.mixTableChange = gp.MixTableChange(
        tempo=gp.MixTableItem(value=100, duration=0))
    note = gp.Note(beat, value=8, string=6)
    note.type = gp.NoteType.normal
    note.effect.hammer = True
    note.effect.slides = [gp.SlideType.shiftSlideTo]
    beat.notes.append(note)
    voice.beats.append(beat)

    out = tmp_path / "smoke.gp5"
    gp.write(song, str(out))
    back = gp.parse(str(out))

    b = back.tracks[0].measures[0].voices[0].beats[0]
    assert b.duration.value == 1
    assert b.text == "C"
    assert b.effect.pickStroke == gp.BeatStrokeDirection.down
    assert b.effect.mixTableChange.tempo.value == 100
    n = b.notes[0]
    assert (n.string, n.value) == (6, 8)
    assert n.effect.hammer is True
    assert gp.SlideType.shiftSlideTo in n.effect.slides
    assert back.measureHeaders[0].marker.title == "Daily bpm=120"
    assert back.tempo == 120
