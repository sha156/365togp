"""练习乐句 JSON 的加载与校验（识谱产物 → build 的输入契约）。

用法: python src/phrase_schema.py <json...>   逐个校验并打印 OK
"""
import json
import pathlib
import sys
from fractions import Fraction

VALID_DURATIONS = {1, 2, 4, 8, 16, 32}
VALID_TECHNIQUES = {"hammer_on", "pull_off", "slide"}
VALID_PICKS = {"down", "up"}


class PhraseError(ValueError):
    """JSON 不符合乐句 schema。"""


def load_phrase(path: "str | pathlib.Path") -> dict:
    data = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    errors = validate_phrase(data)
    if errors:
        raise PhraseError(f"{path}: " + "; ".join(errors))
    return data


def validate_phrase(data: dict) -> list[str]:
    errors = [f"缺少字段 {k}" for k in
              ("label", "title", "tempo", "time_signature", "measures") if k not in data]
    if errors:
        return errors
    if not (isinstance(data["tempo"], int) and 30 <= data["tempo"] <= 300):
        errors.append(f"tempo 非法: {data['tempo']!r}")
    ts = data["time_signature"]
    if not (isinstance(ts, list) and len(ts) == 2 and all(isinstance(x, int) for x in ts)):
        errors.append(f"time_signature 非法: {ts!r}")
        return errors
    if not data["measures"]:
        errors.append("measures 为空")
    for mi, measure in enumerate(data["measures"], 1):
        errors.extend(_measure_errors(mi, measure, Fraction(ts[0], ts[1])))
    return errors


def _measure_errors(mi: int, measure: dict, expected: Fraction) -> list[str]:
    beats = measure.get("beats", [])
    if not beats:
        return [f"小节{mi}: beats 为空"]
    errors = []
    total = Fraction(0)
    for bi, beat in enumerate(beats, 1):
        errors.extend(_beat_errors(mi, bi, beat))
        if beat.get("duration") in VALID_DURATIONS:
            total += _beat_length(beat)
    if not errors and total != expected:
        errors.append(f"小节{mi}: 时值之和 {total} != 拍号 {expected}")
    return errors


def _beat_length(beat: dict) -> Fraction:
    length = Fraction(1, beat["duration"])
    if beat.get("dotted"):
        length *= Fraction(3, 2)
    if beat.get("tuplet"):
        enters, times = beat["tuplet"]
        length *= Fraction(times, enters)
    return length


def _beat_errors(mi: int, bi: int, beat: dict) -> list[str]:
    errors = []
    where = f"小节{mi} 拍{bi}"
    if beat.get("duration") not in VALID_DURATIONS:
        errors.append(f"{where}: duration 非法 {beat.get('duration')!r}")
    if beat.get("pick") is not None and beat.get("pick") not in VALID_PICKS:
        errors.append(f"{where}: pick 非法 {beat['pick']!r}")
    tuplet = beat.get("tuplet")
    if tuplet is not None and not (isinstance(tuplet, list) and len(tuplet) == 2
                                   and all(isinstance(x, int) and x > 0 for x in tuplet)):
        errors.append(f"{where}: tuplet 非法 {tuplet!r}")
    if not beat.get("rest") and not beat.get("notes"):
        errors.append(f"{where}: 既无 notes 也非 rest")
    for note in beat.get("notes", []):
        s, f = note.get("string"), note.get("fret")
        if not (isinstance(s, int) and 1 <= s <= 6):
            errors.append(f"{where}: string 非法 {s!r}")
        if not (isinstance(f, int) and 0 <= f <= 24):
            errors.append(f"{where}: fret 非法 {f!r}")
        for tech in note.get("techniques", []):
            if tech not in VALID_TECHNIQUES:
                errors.append(f"{where}: technique 非法 {tech!r}")
    return errors


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        load_phrase(arg)
        print(f"OK {arg}")
