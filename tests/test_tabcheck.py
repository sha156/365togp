"""tabcheck 单元测试。"""
import json

import pytest

from tabcheck import check_phrase, midi_pitch, note_name, detect_key


def test_midi_pitch():
    assert midi_pitch(6, 0) == 40  # E2
    assert midi_pitch(1, 0) == 64  # E4
    assert midi_pitch(5, 5) == 50  # A2 + 5 = D3
    assert midi_pitch(3, 12) == 67  # G3 + 12 = G4


def test_note_name():
    assert note_name(40) == "E2"
    assert note_name(60) == "C4"
    assert note_name(69) == "A4"


def test_detect_key():
    assert detect_key("C大调音阶（Ｇ型）") == {"root": 0, "mode": "major", "name": "C大调"}
    assert detect_key("Am 分解和弦") == {"root": 9, "mode": "minor", "name": "Am小调"}
    assert detect_key("G Major Scale") == {"root": 7, "mode": "major", "name": "G大调"}
    assert detect_key("没有调性信息的标题") is None


def test_phrase_no_issues():
    phrase = {
        "label": "测试",
        "title": "C大调音阶",
        "tempo": 80,
        "time_signature": [4, 4],
        "measures": [{"beats": [
            {"duration": 8, "notes": [{"string": 6, "fret": 0}]},   # E2
            {"duration": 8, "notes": [{"string": 6, "fret": 3}]},   # G2
            {"duration": 8, "notes": [{"string": 5, "fret": 2}]},   # B2
            {"duration": 8, "notes": [{"string": 5, "fret": 3}]},   # C3
        ]}],
    }
    findings = check_phrase(phrase)
    assert findings == [], f"Expected no findings, got {findings}"


def test_out_of_range_pitch():
    phrase = {
        "label": "测试",
        "title": "测试",
        "time_signature": [4, 4],
        "measures": [{"beats": [
            {"duration": 4, "notes": [{"string": 1, "fret": 30}]},  # fret > 24
        ]}],
    }
    findings = check_phrase(phrase)
    assert len(findings) == 1
    assert "音域" in findings[0]["what"]


def test_big_jump_detected():
    phrase = {
        "label": "测试",
        "title": "测试",
        "time_signature": [4, 4],
        "measures": [{"beats": [
            {"duration": 4, "notes": [{"string": 6, "fret": 0}]},   # E2
            {"duration": 4, "notes": [{"string": 1, "fret": 24}]},  # E6 (2 octaves up)
        ]}],
    }
    findings = check_phrase(phrase)
    assert len(findings) >= 1
    assert "大跳" in findings[0]["what"]


def test_out_of_key():
    phrase = {
        "label": "测试",
        "title": "C大调音阶",
        "time_signature": [4, 4],
        "measures": [{"beats": [
            {"duration": 4, "notes": [{"string": 5, "fret": 1}]},   # A#2 - not in C major
        ]}],
    }
    findings = check_phrase(phrase)
    assert len(findings) >= 1
    assert "不在" in findings[0]["what"]


def test_cross_string_ok():
    """跨弦练习应有大跳但不应触发警告。"""
    phrase = {
        "label": "每日必弹",
        "title": "⑥弦→⑤弦的跨弦基础乐句",
        "tempo": 120,
        "time_signature": [4, 4],
        "measures": [{"beats": [
            {"duration": 8, "notes": [{"string": 6, "fret": 8}]},
            {"duration": 8, "notes": [{"string": 5, "fret": 7}]},
            {"duration": 8, "notes": [{"string": 6, "fret": 8}]},
            {"duration": 8, "notes": [{"string": 5, "fret": 8}]},
            {"duration": 8, "notes": [{"string": 6, "fret": 8}]},
            {"duration": 8, "notes": [{"string": 5, "fret": 10}]},
            {"duration": 8, "notes": [{"string": 4, "fret": 7}]},
            {"duration": 8, "notes": [{"string": 6, "fret": 8}]},
        ]}],
    }
    findings = check_phrase(phrase)
    # Cross-string octave jumps should not trigger (threshold is 24 semitones)
    big_jumps = [f for f in findings if "大跳" in f["what"]]
    assert len(big_jumps) == 0, f"False positives: {big_jumps}"
