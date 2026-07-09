"""tab_reader 高清管线回归：锁定 470dpi 新 PDF 渲染 + 重建模板库(work/templates/hires)
在 week09_hires 切图上的成果。缺 work/ 资源则跳过（work/ 不入库）。

基线（2026-07-09 高清迁移后，reconcile 全绿准确率）：
  sys01 每日 100%(32/32 零弦错零品错) · sys02 周一 96.7% · sys03 周二 100%
  sys04/sys05 受音符符干干扰 + GT 存疑，留待音频对账，本文件不锁其数值。
"""
import json
import pathlib

import pytest

from reconcile import reconcile
from tab_reader import read_system

ROOT = pathlib.Path(__file__).resolve().parent.parent
HIRES = ROOT / "work" / "phrases" / "week09_hires"
JSON = ROOT / "work" / "json" / "week09"
BANK = ROOT / "work" / "templates" / "hires"

pytestmark = pytest.mark.skipif(
    not (HIRES.exists() and JSON.exists() and BANK.exists()),
    reason="需要 work/ 下 week09_hires 切图、week09 GT 与 hires 模板库")


def _gt(name):
    data = json.loads((JSON / f"{name}.json").read_text(encoding="utf-8"))
    return [(n["string"], n["fret"]) for m in data["measures"]
            for b in m["beats"] for n in b.get("notes", [])]


def test_hires_sys01_exact():
    """高清 sys01：检测数=GT 且逐音(弦,品)全对，零低分。"""
    r = read_system(str(HIRES / "system_01.png"), str(BANK))
    det = [(d["string"], d["fret"]) for d in sorted(r["detections"], key=lambda d: d["cx"])]
    assert det == _gt("01_daily")
    assert all(not d["low_conf"] for d in r["detections"])


def test_hires_sys01_reconcile_100():
    res = reconcile(str(HIRES / "system_01.png"), str(JSON / "01_daily.json"), str(BANK))
    s = res["summary"]
    assert s["string"] == 0 and s["fret"] == 0
    assert s["ok"] == s["gt"] == 32


def test_hires_sys02_no_string_errors_high_acc():
    res = reconcile(str(HIRES / "system_02.png"), str(JSON / "02_monday.json"), str(BANK))
    s = res["summary"]
    assert s["string"] == 0            # 零弦错
    assert s["accuracy"] >= 0.95       # ≥95%（实测 96.7%）


def test_hires_sys03_perfect():
    res = reconcile(str(HIRES / "system_03.png"), str(JSON / "03_tuesday.json"), str(BANK))
    s = res["summary"]
    assert s["string"] == 0 and s["fret"] == 0
    assert s["ok"] == s["gt"] == 60
