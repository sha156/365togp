import pytest

from phrase_schema import PhraseError, load_phrase, validate_phrase


def minimal_phrase() -> dict:
    return {
        "label": "周一",
        "title": "测试乐句",
        "tempo": 100,
        "time_signature": [4, 4],
        "measures": [
            {"chord": "C",
             "beats": [{"duration": 1,
                        "notes": [{"string": 3, "fret": 10}]}]}
        ],
    }


def test_valid_phrase_passes():
    assert validate_phrase(minimal_phrase()) == []


def test_missing_field_reported():
    p = minimal_phrase()
    del p["tempo"]
    assert any("tempo" in e for e in validate_phrase(p))


def test_bad_fret_reported():
    p = minimal_phrase()
    p["measures"][0]["beats"][0]["notes"][0]["fret"] = 99
    assert any("fret" in e for e in validate_phrase(p))


def test_incomplete_measure_reported():
    p = minimal_phrase()
    p["measures"][0]["beats"][0]["duration"] = 4  # 4/4 里只有一个四分音符
    assert any("时值" in e for e in validate_phrase(p))


def test_dotted_and_tuplet_fill_measure():
    p = minimal_phrase()
    p["measures"][0]["beats"] = (
        [{"duration": 2, "dotted": True, "notes": [{"string": 3, "fret": 5}]}]   # 3/4
        + [{"duration": 8, "tuplet": [3, 2],
            "notes": [{"string": 3, "fret": 5}]}] * 3                            # 1/4
    )
    assert validate_phrase(p) == []


def test_load_phrase_raises_on_invalid(tmp_path):
    f = tmp_path / "bad.json"
    f.write_text('{"label": "x"}', encoding="utf-8")
    with pytest.raises(PhraseError):
        load_phrase(f)
