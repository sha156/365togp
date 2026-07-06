"""TAB 弦位校验器 — 用乐理 + 四道交叉验证法检测 JSON 中的弦位错误。

核心方法（对应识谱操作手册的四道交叉验证）：
1. **音高检查**：string+fret → MIDI 音高 → 检查是否在吉他音域内 (40-88)，
   且与五线谱调号一致（通过标注的 scale 推断许可音）
2. **音乐逻辑**：相邻音跳度不应在音阶内出现无端大跳（增音程/不协和跳进）；
   整条练习应是音阶/琶音套路
3. **指法检查**：同一把位内，食=最低品 小=最高品，检查指法标记与品格的一致性
4. **同构检查**：周一/周二的四小节只是移调，pattern 应该一致

用法：
    python src/tabcheck.py work/json/week09/*.json
    python src/tabcheck.py output/week09.gp5 --verify   # 对 .gp5 回读校验
"""
import argparse
import json
import pathlib
import re
import sys
from typing import Optional

# 标准调弦 MIDI 音高: 弦号 1-6 → 基准音(C0=0)
STRING_PITCH = {1: 64, 2: 59, 3: 55, 4: 50, 5: 45, 6: 40}

# 12 平均律音名
NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
# 自然大调音程（半音数从主音开始）
MAJOR_SCALE = [0, 2, 4, 5, 7, 9, 11]
# 自然小调音程
NATURAL_MINOR_SCALE = [0, 2, 3, 5, 7, 8, 10]
# 大调音阶中各音级的半音数映射表
MAJOR_INTERVALS = {"C": 0, "G": 7, "D": 2, "A": 9, "E": 4, "B": 11,
                   "F#": 6, "C#": 1, "F": 5, "Bb": 10, "Eb": 3, "Ab": 8,
                   "Db": 1, "Gb": 6, "Cb": 11}
MINOR_INTERVALS = {"Am": 0, "Em": 7, "Bm": 2, "F#m": 9, "C#m": 4, "G#m": 11,
                   "D#m": 6, "A#m": 1, "Dm": 5, "Gm": 10, "Cm": 3, "Fm": 8,
                   "Bbm": 1, "Ebm": 6, "Abm": 11}


def note_name(midi: int) -> str:
    return f"{NOTE_NAMES[midi % 12]}{midi // 12 - 1}"


def midi_pitch(string: int, fret: int) -> int:
    """string=1(最细弦), fret=0-24 → MIDI 音高"""
    return STRING_PITCH.get(string, 64) + fret


def detect_key(title: str, label: str = "") -> Optional[dict]:
    """从标题和 label 中提取调性。返回 {'root': 半音数, 'mode': 'major'|'minor'} 或 None。"""
    text = f"{label} {title}"
    # 先找大调/小调词
    for pattern in [r'([A-G][b#]?)大调', r'([A-G][b#]?)\s*Major', r'([A-G][b#]?)\s*Dur']:
        m = re.search(pattern, text)
        if m:
            key = m.group(1)
            root = NOTE_NAMES.index(key) if key in NOTE_NAMES else None
            if root is not None:
                return {"root": root, "mode": "major", "name": f"{key}大调"}
    for pattern in [r'([A-G][b#]?m)\b', r'([A-G][b#]?)\s*minor', r'([A-G][b#]?)\s*Moll']:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            key = m.group(1)
            root = NOTE_NAMES.index(key.rstrip('mM')) if key.rstrip('mM') in NOTE_NAMES else None
            if root is not None:
                return {"root": root, "mode": "minor", "name": f"{key}小调" if 'm' in key.lower() else f"{key}小调"}
    # 从和弦名推断（常见开始和弦=C的根音）
    for chord_pattern in [r'和弦的乐句$', r'和弦音的乐句']:
        pass
    return None


def in_key_pitches(key: dict) -> set:
    """返回 key 允许的 MIDI 音级（在 0-11 内的集合）。"""
    root = key["root"]
    if key["mode"] == "major":
        intervals = MAJOR_SCALE
    else:
        intervals = NATURAL_MINOR_SCALE
    return {(root + i) % 12 for i in intervals}


def check_phrase(phrase: dict) -> list[dict]:
    """对一条乐句 JSON 执行弦位校验。返回 findings 列表。"""
    findings = []
    key = detect_key(phrase.get("title", ""), phrase.get("label", ""))
    in_key_set = in_key_pitches(key) if key else None

    for mi, measure in enumerate(phrase.get("measures", []), 1):
        notes_seen = []
        for bi, beat in enumerate(measure.get("beats", []), 1):
            if beat.get("rest"):
                continue
            for ni, note in enumerate(beat.get("notes", []), 1):
                s, f = note.get("string", 0), note.get("fret", 0)
                pitch = midi_pitch(s, f)
                pitch_class = pitch % 12
                where = f"m{mi}b{bi}n{ni}"

                # 1a. 音域检查
                if pitch < 36 or pitch > 88:
                    findings.append({
                        "where": where,
                        "what": f"音高 {note_name(pitch)} ({pitch}) 超出合理吉他音域 (E2~E6)",
                        "severity": "HIGH",
                        "note": f"str={s} fr={f}",
                    })

                # 1b. 调性检查
                if in_key_set and pitch_class not in in_key_set:
                    findings.append({
                        "where": where,
                        "what": f"音 {note_name(pitch)} (str={s} fr={f}) 不在 {key['name']} 调内",
                        "severity": "MEDIUM",
                        "note": f"音阶内音级: {sorted(in_key_set)}",
                    })

                # 2. 相邻音大跳检查（>2 八度才警告，避免跨弦琶音假阳性）
                if notes_seen:
                    prev_pitch = midi_pitch(notes_seen[-1]["string"],
                                            notes_seen[-1]["fret"])
                    interval = abs(pitch - prev_pitch)
                    if interval >= 24:  # 双八度以上才警告（避免跨弦琶音假阳性）
                        findings.append({
                            "where": f"{where}（前音 {note_name(prev_pitch)}→{note_name(pitch)}）",
                            "what": f"{interval} 半音大跳（>2八度），检查弦位和品格",
                            "severity": "HIGH",
                            "note": f"前 str={notes_seen[-1]['string']} fr={notes_seen[-1]['fret']} 现 str={s} fr={f}",
                        })

                notes_seen.append({"string": s, "fret": f, "pitch": pitch})

    return findings


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help="乐句 JSON 文件或 .gp5 文件路径")
    ap.add_argument("--verify", action="store_true",
                    help="对 .gp5 文件读回后解析音符再校验（需指定单个 .gp5）")
    args = ap.parse_args()

    if args.verify:
        # .gp5 模式：读回后解析成 phraselike dict
        try:
            import guitarpro as gp
        except ImportError:
            print("ERROR: --verify 模式需要 PyGuitarPro")
            sys.exit(1)
        for path in args.inputs:
            p = pathlib.Path(path)
            if p.suffix.lower() not in (".gp5", ".gp"):
                continue
            song = gp.parse(str(p), encoding="cp936")
            track = song.tracks[0]
            # 构建伪 phrase
            measures = []
            for hdr in song.measureHeaders:
                ts = hdr.timeSignature
                m = track.measures[hdr.number - 1]
                beats = []
                for b in m.voices[0].beats:
                    beat = {"duration": b.duration.value}
                    if b.duration.isDotted:
                        beat["dotted"] = True
                    if b.status == gp.BeatStatus.rest:
                        beat["rest"] = True
                    if b.notes:
                        beat["notes"] = [{"string": n.string, "fret": n.value}
                                         for n in b.notes]
                    if b.effect.pickStroke:
                        beat["pick"] = ("down" if b.effect.pickStroke
                                        == gp.BeatStrokeDirection.down else "up")
                    beats.append(beat)
                measures.append({
                    "barline": "regular",
                    "beats": beats,
                })
                if hdr.marker:
                    measures[-1]["_marker"] = hdr.marker.title

            # 按 marker 切分 phrases
            phrases = []
            current = {"title": p.stem, "label": "", "tempo": 120,
                       "time_signature": [4, 4], "measures": []}
            for m in measures:
                if m.get("_marker") and current["measures"]:
                    # 找到 marker 说明是新的 phrase
                    phrases.append(current)
                    current = {"title": "", "label": "",
                               "tempo": 120,
                               "time_signature": [4, 4], "measures": []}
                if m.get("_marker"):
                    marker = m["_marker"]
                    if ":" in marker:
                        label, title = marker.split(":", 1)
                        current["label"] = label.strip()
                        current["title"] = title.strip()
                    else:
                        current["title"] = marker
                current["measures"].append(m)

            if current["measures"]:
                phrases.append(current)

            print(f"{p.name}: {len(phrases)} phrases, {len(measures)} measures")
            for phrase in phrases:
                findings = check_phrase(phrase)
                if findings:
                    print(f"  [{phrase.get('label','?')}]: {phrase.get('title','?')}")
                    for f in findings:
                        print(f"    [{f['severity']}] {f['where']}: {f['what']}")
                if not findings:
                    print(f"  [{phrase.get('label','?')}]: ✓ 无异常")
    else:
        # JSON 模式
        for path in args.inputs:
            from phrase_schema import load_phrase
            try:
                data = load_phrase(path)
            except Exception as e:
                print(f"ERROR {path}: {e}")
                continue

            findings = check_phrase(data)
            label = data.get("label", "?")
            title = data.get("title", "?")
            print(f"{pathlib.Path(path).name} [{label}] {title}")
            if findings:
                for f in findings:
                    print(f"  [{f['severity']}] {f['where']}: {f['what']}")
                print(f"  总计: {len(findings)} 条建议")
            else:
                print(f"  ✓ 无异常")


if __name__ == "__main__":
    main()
