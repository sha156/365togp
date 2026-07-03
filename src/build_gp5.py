"""把一周的乐句 JSON 构建成单个 .gp5 文件。

用法: python src/build_gp5.py work/json/week09 -o output/week09.gp5 --title "Week09 Picking"
JSON 按文件名排序（01_daily.json, 02_monday.json, ...）依次拼接。

注意：GP5 字符串按系统码页解码；本项目面向中文 Windows，统一用 cp936（GBK）
写入，中文 marker/标题可正常显示。读回时同样需要 encoding="cp936"。
"""
import argparse
import pathlib

import guitarpro as gp

from phrase_schema import load_phrase

GP5_ENCODING = "cp936"
PICK_MAP = {"down": gp.BeatStrokeDirection.down, "up": gp.BeatStrokeDirection.up}


def build_week(json_dir: str, out_path: str, title: str) -> gp.Song:
    files = sorted(pathlib.Path(json_dir).glob("*.json"))
    if not files:
        raise ValueError(f"{json_dir} 下没有 JSON 文件")
    phrases = [load_phrase(f) for f in files]

    song = gp.Song()
    song.title = title
    song.tempo = phrases[0]["tempo"]
    track = song.tracks[0]
    track.name = "Electric Guitar"
    track.channel.instrument = 30  # Distortion Guitar

    total = sum(len(p["measures"]) for p in phrases)
    while len(track.measures) < total:
        song.newMeasure()

    start = 0
    for phrase in phrases:
        _write_phrase(song, track, phrase, start)
        start += len(phrase["measures"])

    pathlib.Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    gp.write(song, out_path, encoding=GP5_ENCODING)
    return song


def _write_phrase(song: gp.Song, track: gp.Track, phrase: dict, start: int) -> None:
    num, den = phrase["time_signature"]
    for offset, measure_data in enumerate(phrase["measures"]):
        header = song.measureHeaders[start + offset]
        header.timeSignature.numerator = num
        header.timeSignature.denominator.value = den
        if offset == 0:
            marker_title = f"{phrase['label']}: {phrase['title']} bpm={phrase['tempo']}"
            header.marker = gp.Marker(title=marker_title)
        _write_measure(track.measures[start + offset], measure_data,
                       phrase["tempo"], set_tempo=offset == 0)


def _write_measure(measure: gp.Measure, measure_data: dict,
                   tempo: int, set_tempo: bool) -> None:
    voice = measure.voices[0]
    for bi, beat_data in enumerate(measure_data["beats"]):
        beat = gp.Beat(voice)
        beat.duration = gp.Duration(
            value=beat_data["duration"], isDotted=bool(beat_data.get("dotted")))
        if beat_data.get("tuplet"):
            enters, times = beat_data["tuplet"]
            beat.duration.tuplet = gp.Tuplet(enters=enters, times=times)
        beat.status = (gp.BeatStatus.rest if beat_data.get("rest")
                       else gp.BeatStatus.normal)
        if beat_data.get("pick"):
            beat.effect.pickStroke = PICK_MAP[beat_data["pick"]]
        if bi == 0 and measure_data.get("chord"):
            beat.text = measure_data["chord"]
        if bi == 0 and set_tempo:
            beat.effect.mixTableChange = gp.MixTableChange(
                tempo=gp.MixTableItem(value=tempo, duration=0))
        for note_data in beat_data.get("notes", []):
            beat.notes.append(_make_note(beat, note_data))
        voice.beats.append(beat)


def _make_note(beat: gp.Beat, note_data: dict) -> gp.Note:
    note = gp.Note(beat, value=note_data["fret"], string=note_data["string"])
    note.type = gp.NoteType.tie if note_data.get("tied") else gp.NoteType.normal
    for tech in note_data.get("techniques", []):
        if tech in ("hammer_on", "pull_off"):
            note.effect.hammer = True
        elif tech == "slide":
            note.effect.slides.append(gp.SlideType.shiftSlideTo)
    return note


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("json_dir")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--title", required=True)
    args = ap.parse_args()
    song = build_week(args.json_dir, args.out, args.title)
    print(f"已写入 {args.out}: {len(song.tracks[0].measures)} 小节")


if __name__ == "__main__":
    main()
