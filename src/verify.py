"""读回 .gp5 打印 ASCII TAB，供与原书切图逐小节比对。

用法: python src/verify.py output/week09.gp5 [> work/verify_week09.txt]
"""
import argparse

import guitarpro as gp

GP5_ENCODING = "cp936"  # 与 build_gp5 一致，支持中文 marker
PICK_ABBR = {gp.BeatStrokeDirection.down: "v", gp.BeatStrokeDirection.up: "^"}


def _note_mark(note: gp.Note) -> str:
    mark = str(note.value)
    if note.type == gp.NoteType.tie:
        mark = f"({mark})"
    if note.effect.hammer:
        mark += "h"
    if note.effect.slides:
        mark += "s"
    return mark


def _beat_cells(beat: gp.Beat) -> tuple[str, dict[int, str]]:
    cells = {s: "-" for s in range(1, 7)}
    for note in beat.notes:
        cells[note.string] = _note_mark(note)
    dur = str(beat.duration.value)
    if beat.duration.isDotted:
        dur += "."
    if beat.duration.tuplet.enters != 1:
        dur += f"({beat.duration.tuplet.enters})"
    pick_dir = PICK_ABBR.get(beat.effect.pickStroke, "")
    dur += pick_dir
    if beat.status == gp.BeatStatus.rest:
        dur += "r"
    if beat.text:
        dur += f" [{beat.text}]"
    return dur, cells


def ascii_tab(song: gp.Song) -> str:
    out = []
    for mi, measure in enumerate(song.tracks[0].measures, 1):
        if measure.header.marker:
            out.append(f"\n== {measure.header.marker.title} ==")
        durs, rows = [], {s: [] for s in range(1, 7)}
        for beat in measure.voices[0].beats:
            dur, cells = _beat_cells(beat)
            width = max(len(dur), *(len(c) for c in cells.values())) + 1
            durs.append(dur.ljust(width))
            for s in rows:
                rows[s].append(cells[s].ljust(width, "-"))
        out.append(f"-- 小节 {mi} --")
        out.append("t: " + "".join(durs))
        for s in range(1, 7):
            out.append(f"{s}|" + "".join(rows[s]))
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("gp5")
    args = ap.parse_args()
    print(ascii_tab(gp.parse(args.gp5, encoding=GP5_ENCODING)))


if __name__ == "__main__":
    main()
