import json

import guitarpro as gp

from build_gp5 import build_week
from verify import ascii_tab


def test_ascii_tab_shows_marker_frets_and_techniques(tmp_path):
    d = tmp_path / "json"
    d.mkdir()
    (d / "01_monday.json").write_text(json.dumps({
        "label": "Monday", "title": "Test", "tempo": 100,
        "time_signature": [4, 4],
        "measures": [{"chord": "Dm", "beats": [
            {"duration": 2, "pick": "down",
             "notes": [{"string": 3, "fret": 10, "techniques": ["hammer_on"]}]},
            {"duration": 2, "pick": "up",
             "notes": [{"string": 6, "fret": 8}]},
        ]}],
    }, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "w.gp5"
    build_week(str(d), str(out), "t")

    text = ascii_tab(gp.parse(str(out)))

    assert "Monday" in text          # marker
    assert "Dm" in text              # 和弦名
    assert "10h" in text             # 品格 + hammer 标记
    assert "2v" in text and "2^" in text  # 时值 + 拨向
