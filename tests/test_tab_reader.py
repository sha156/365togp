"""tab_reader 回归：在已验收的 system_01（模板全覆盖 7-10）上锁定
弦位零错 + 检测数=GT数。依赖 work/ 下的切图与模板（不入库），缺失则跳过。
"""
import json
import pathlib

import pytest

from tab_reader import read_system

ROOT = pathlib.Path(__file__).resolve().parent.parent
IMG = ROOT / "work" / "phrases" / "week09" / "system_01.png"
GT = ROOT / "work" / "json" / "week09" / "01_daily.json"
SEED = ROOT / "work" / "templates" / "seed"

pytestmark = pytest.mark.skipif(
    not (IMG.exists() and GT.exists() and SEED.exists()),
    reason="需要 work/ 下的 system_01 切图、01_daily.json 与 seed 模板库")


def _gt_strings():
    data = json.loads(GT.read_text(encoding="utf-8"))
    return [n["string"] for m in data["measures"]
            for b in m["beats"] for n in b.get("notes", [])]


def test_sys01_detect_count_matches_gt():
    r = read_system(str(IMG), str(SEED))
    assert len(r["detections"]) == len(_gt_strings())


def test_sys01_no_string_errors():
    """按 x 顺序，检测弦号应与 GT 弦号逐一吻合（0 弦位归行错）。"""
    r = read_system(str(IMG), str(SEED))
    det_strings = [d["string"] for d in sorted(r["detections"], key=lambda d: d["cx"])]
    gt = _gt_strings()
    assert len(det_strings) == len(gt)
    mism = [(i, g, d) for i, (g, d) in enumerate(zip(gt, det_strings)) if g != d]
    assert not mism, f"弦位不符: {mism}"


def test_sys01_frets_all_correct():
    r = read_system(str(IMG), str(SEED))
    data = json.loads(GT.read_text(encoding="utf-8"))
    gt = [(n["string"], n["fret"]) for m in data["measures"]
          for b in m["beats"] for n in b.get("notes", [])]
    det = [(d["string"], d["fret"]) for d in sorted(r["detections"], key=lambda d: d["cx"])]
    assert det == gt
