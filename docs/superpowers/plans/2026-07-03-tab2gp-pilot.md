# tab2gp 试点（第 9 周 → week09.gp5）实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把《365日！！电吉他手的养成计划》第 9 周的 7 条练习乐句转成一个 Guitar Pro 可打开的 `output/week09.gp5`。

**Architecture:** 五段管线 render→segment→transcribe→build→verify。PyMuPDF 渲染扫描页为 300dpi PNG；OpenCV 按"长横线聚类"切出每条乐句系统块；Claude 视觉识谱产出人可校对的 JSON 中间层；PyGuitarPro 由 JSON 构建 .gp5；verify 读回打印 ASCII TAB 与原图逐小节比对。

**Tech Stack:** Python 3.11（`py -3.11` + venv）、PyMuPDF、OpenCV、PyGuitarPro、pytest。

## Global Constraints

- 一律使用 `.venv\Scripts\python`（由 `py -3.11 -m venv .venv` 创建）；本机默认 python 是 3.9，禁止直接用。
- 试点数据事实：第 9 周跨 PDF 两页，0-based 页码 **20 和 21**；共 **7 条乐句**（每日必弹、周一～周六），周日为纯文字无乐谱。此处修正设计文档中"一页 8 条"的说法。
- 产物路径：中间产物在 `work/`（已被 .gitignore 忽略，转录 JSON 含书内容，**不入库**）；成品在 `output/`（同样忽略）。
- 源 PDF 文件名：`365日！！电吉他手的养成计划.pdf`（位于仓库根目录）。
- 单文件 <400 行、单函数 <50 行；提交信息用 conventional commits（feat/test/fix/docs/chore），不带署名尾注。
- 产出仅供用户个人练习使用，不对外分发。

## 乐句 JSON 契约（所有任务共用）

`work/json/week09/NN_<slug>.json`，文件名前缀决定构建顺序（`01_daily.json`、`02_monday.json`…`07_saturday.json`）。单文件结构：

```json
{
  "label": "周一",
  "title": "跨越2弦弹奏和弦音的乐句",
  "tempo": 100,
  "time_signature": [4, 4],
  "cd_time": "0:11",
  "measures": [
    {
      "chord": "C",
      "beats": [
        {
          "duration": 16,
          "dotted": false,
          "rest": false,
          "pick": "down",
          "tuplet": null,
          "notes": [
            {"string": 3, "fret": 10, "techniques": [], "tied": false, "uncertain": false}
          ]
        }
      ]
    }
  ]
}
```

语义约定：

- `duration`：1/2/4/8/16/32（GP 时值）；`dotted` 附点；`tuplet` 为 `[enters, times]`（如三连音 `[3, 2]`）或 null/省略。
- `string`：1=最细弦（TAB 最上面一线），6=最粗弦；`fret` 0–24。
- `techniques`（记在**发起音**上，即书中 h./p./s. 弧线的前一个音）：`hammer_on`、`pull_off`、`slide`。
- `pick`：`down`（⊓）/ `up`（V）/ null；`rest: true` 时 `notes` 为空。
- `tied: true` 表示与前一音连音线相连（fret 重复填写）；`uncertain: true` 标记识谱拿不准的音，进入人工复核清单。
- 每小节 beats 时值之和必须恰好填满拍号（schema 校验强制）。
- `chord` 为该小节起点的和弦名（无则省略/null）。

---

### Task 1: 环境搭建 + PyGuitarPro API 冒烟往返测试

PyGuitarPro 的字段命名（pickStroke、MixTableChange、Marker、NoteType 默认值等）是本项目最大的 API 假设风险，用一个往返测试一次性锁定全部假设。

**Files:**
- Create: `requirements.txt`
- Create: `conftest.py`
- Create: `tests/test_smoke_pyguitarpro.py`

**Interfaces:**
- Produces: 可用的 `.venv`；被验证的 PyGuitarPro 用法模式（后续 Task 5/6 的代码直接沿用本测试中的 API 调用方式）。

- [ ] **Step 1: 创建 venv 并安装依赖**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install pymupdf opencv-python numpy PyGuitarPro pytest
```

- [ ] **Step 2: 写 requirements.txt 与 conftest.py**

`requirements.txt`：

```
pymupdf>=1.24
opencv-python>=4.9
numpy>=1.26
PyGuitarPro>=0.9.3
pytest>=8
```

`conftest.py`（仓库根目录，让测试能直接 `from render import ...` 导入 src 下模块）：

```python
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent / "src"))
```

- [ ] **Step 3: 写冒烟往返测试**

`tests/test_smoke_pyguitarpro.py`：

```python
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
    header.marker = gp.Marker(title="每日必弹 ♩=120")

    voice = track.measures[0].voices[0]
    beat = gp.Beat(voice)
    beat.status = gp.BeatStatus.normal
    beat.duration = gp.Duration(value=1)  # 全音符，填满 4/4
    beat.text = gp.BeatText(value="C")
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
    assert b.text.value == "C"
    assert b.effect.pickStroke == gp.BeatStrokeDirection.down
    assert b.effect.mixTableChange.tempo.value == 100
    n = b.notes[0]
    assert (n.string, n.value) == (6, 8)
    assert n.effect.hammer is True
    assert gp.SlideType.shiftSlideTo in n.effect.slides
    assert back.measureHeaders[0].marker.title == "每日必弹 ♩=120"
    assert back.tempo == 120
```

- [ ] **Step 4: 运行测试**

Run: `.venv\Scripts\python -m pytest tests/test_smoke_pyguitarpro.py -v`
Expected: PASS。若因字段名报 AttributeError/TypeError（如 `pickStroke`、`MixTableItem` 签名不符），打开 `.venv\Lib\site-packages\guitarpro\models.py` 查对应类的真实定义，修正测试中的用法并记录——**以真实 API 为准**，后续任务沿用修正后的写法。

- [ ] **Step 5: Commit**

```powershell
git add requirements.txt conftest.py tests/test_smoke_pyguitarpro.py
git commit -m "test: PyGuitarPro 冒烟往返测试锁定 API 假设"
```

---

### Task 2: render.py — PDF 页渲染

**Files:**
- Create: `src/render.py`
- Test: `tests/test_render.py`

**Interfaces:**
- Produces: `render_page(pdf_path: str, page_index: int, out_dir: str, dpi: int = 300) -> pathlib.Path`，输出 `work/pages/p{page:03d}.png`；CLI `python src/render.py <pdf> <page...> -o work/pages`。

- [ ] **Step 1: 写失败测试**

`tests/test_render.py`：

```python
import fitz
import pytest

from render import render_page

PDF = "365日！！电吉他手的养成计划.pdf"


def test_render_page_creates_300dpi_png(tmp_path):
    out = render_page(PDF, 20, str(tmp_path))
    assert out.name == "p020.png"
    assert out.exists()
    pix = fitz.Pixmap(str(out))
    assert pix.width > 2000  # 300dpi 整页扫描宽应远超 2000px


def test_render_page_rejects_bad_index(tmp_path):
    with pytest.raises(ValueError):
        render_page(PDF, 999, str(tmp_path))
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_render.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'render'`

- [ ] **Step 3: 实现 src/render.py**

```python
"""把扫描版 PDF 的指定页渲染成 300dpi PNG。

用法: python src/render.py <pdf> <page...> -o work/pages   （页码为 0-based）
"""
import argparse
import pathlib

import fitz


def render_page(pdf_path: str, page_index: int, out_dir: str, dpi: int = 300) -> pathlib.Path:
    doc = fitz.open(pdf_path)
    if not 0 <= page_index < doc.page_count:
        raise ValueError(f"page_index {page_index} 超出范围 0..{doc.page_count - 1}")
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"p{page_index:03d}.png"
    doc[page_index].get_pixmap(dpi=dpi).save(str(target))
    return target


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pdf")
    ap.add_argument("pages", nargs="+", type=int, help="0-based 页码，可多个")
    ap.add_argument("-o", "--out", default="work/pages")
    ap.add_argument("--dpi", type=int, default=300)
    args = ap.parse_args()
    for page in args.pages:
        print(render_page(args.pdf, page, args.out, args.dpi))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_render.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```powershell
git add src/render.py tests/test_render.py
git commit -m "feat: render.py 渲染 PDF 页为 300dpi PNG"
```

---

### Task 3: segment.py — 乐句系统切图

**Files:**
- Create: `src/segment.py`
- Test: `tests/test_segment.py`

**Interfaces:**
- Consumes: Task 2 的 `render_page`（测试 fixture 中渲染真实页）。
- Produces: `segment_page(page_png: str, out_dir: str, start_index: int = 1) -> list[pathlib.Path]`，每个系统输出 `system_NN.png` 和 `system_NN@2x.png`；CLI `python src/segment.py <page.png...> -o work/phrases/week09`（多页连续编号）。

原理：谱线是横贯页面大半宽度的黑色横线。形态学开运算只保留长横线 → 按行聚类成"谱线" → 谱线再按间距聚类成"系统"（五线谱 5 条 + TAB 6 条 ≈ 11 条线）；标题栏方框等少线簇被 `MIN_LINES_PER_SYSTEM` 过滤。裁切上方多留边容纳和弦名/速度记号。

- [ ] **Step 1: 写失败测试（用真实页做集成测试）**

`tests/test_segment.py`：

```python
import pytest

from render import render_page
from segment import segment_page

PDF = "365日！！电吉他手的养成计划.pdf"


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("pages")
    return [render_page(PDF, i, str(d)) for i in (20, 21)]


def test_page20_has_4_systems(pages, tmp_path):
    saved = segment_page(str(pages[0]), str(tmp_path / "w"))
    assert len(saved) == 4  # 每日必弹 + 周一/二/三
    assert saved[0].name == "system_01.png"
    assert (tmp_path / "w" / "system_01@2x.png").exists()


def test_page21_has_3_systems(pages, tmp_path):
    saved = segment_page(str(pages[1]), str(tmp_path / "w"), start_index=5)
    assert len(saved) == 3  # 周四/五/六（周日无谱）
    assert saved[0].name == "system_05.png"
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_segment.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'segment'`

- [ ] **Step 3: 实现 src/segment.py**

```python
"""从整页 PNG 中定位并裁出每条乐句（五线谱+TAB 系统块）。

用法: python src/segment.py <page.png...> -o work/phrases/week09
"""
import argparse
import pathlib

import cv2
import numpy as np

# 针对 300dpi 扫描页的经验参数
MIN_LINE_WIDTH_RATIO = 0.35   # 谱线至少横贯页宽的 35%
LINE_GAP = 12                 # 行间隔 <=12px 归为同一条谱线
SYSTEM_GAP = 120              # 谱线间隔 <=120px 归入同一系统
MIN_LINES_PER_SYSTEM = 9      # 5+6=11 条，容忍漏检到 9
PAD_TOP = 130                 # 上边留白：和弦名、连音弧线
PAD_BOTTOM = 40


def _cluster(sorted_vals: np.ndarray, max_gap: int) -> list[tuple[int, int]]:
    """把升序整数序列按间隔聚类，返回每簇 (min, max)。"""
    out = []
    start = prev = int(sorted_vals[0])
    for v in sorted_vals[1:]:
        v = int(v)
        if v - prev > max_gap:
            out.append((start, prev))
            start = v
        prev = v
    out.append((start, prev))
    return out


def find_systems(gray: np.ndarray) -> list[tuple[int, int]]:
    """返回每个谱表系统的 (y_top, y_bottom)。"""
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    kernel_w = int(gray.shape[1] * MIN_LINE_WIDTH_RATIO)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
    long_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    rows = np.where(long_lines.sum(axis=1) > 0)[0]
    if len(rows) == 0:
        return []
    lines = _cluster(rows, LINE_GAP)
    centers = np.array([(a + b) // 2 for a, b in lines])
    systems = []
    for lo, hi in _cluster(centers, SYSTEM_GAP):
        n = int(((centers >= lo) & (centers <= hi)).sum())
        if n >= MIN_LINES_PER_SYSTEM:
            systems.append((lo, hi))
    return systems


def segment_page(page_png: str, out_dir: str, start_index: int = 1) -> list[pathlib.Path]:
    gray = cv2.imread(page_png, cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"无法读取图像: {page_png}")
    out = pathlib.Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    saved = []
    for i, (top, bottom) in enumerate(find_systems(gray), start=start_index):
        y0 = max(0, top - PAD_TOP)
        y1 = min(gray.shape[0], bottom + PAD_BOTTOM)
        crop = gray[y0:y1, :]
        target = out / f"system_{i:02d}.png"
        cv2.imwrite(str(target), crop)
        big = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        cv2.imwrite(str(out / f"system_{i:02d}@2x.png"), big)
        saved.append(target)
    return saved


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("pages", nargs="+", help="整页 PNG，按书页顺序")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    idx = 1
    for page in args.pages:
        saved = segment_page(page, args.out, start_index=idx)
        idx += len(saved)
        for s in saved:
            print(s)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: 运行确认通过（必要时调参）**

Run: `.venv\Scripts\python -m pytest tests/test_segment.py -v`
Expected: 2 passed。若系统数不符：在 `find_systems` 里临时 print 每簇的谱线数与 y 范围，按输出微调 `SYSTEM_GAP` / `MIN_LINES_PER_SYSTEM` / `MIN_LINE_WIDTH_RATIO`（试点只要求这两页可用）。调参后目视抽查一张 `system_NN.png` 确认切图完整（含和弦名与整条 TAB）。

- [ ] **Step 5: Commit**

```powershell
git add src/segment.py tests/test_segment.py
git commit -m "feat: segment.py 按谱线聚类切出乐句系统块"
```

---

### Task 4: phrase_schema.py — 乐句 JSON 校验

**Files:**
- Create: `src/phrase_schema.py`
- Test: `tests/test_phrase_schema.py`

**Interfaces:**
- Produces: `load_phrase(path) -> dict`（校验失败抛 `PhraseError`，消息含所有错误）；`validate_phrase(data: dict) -> list[str]`；CLI `python src/phrase_schema.py <json...>` 逐个校验并打印 OK。
- 契约即本文开头"乐句 JSON 契约"。核心校验：必填字段、取值域、**每小节时值之和恰好填满拍号**（用 Fraction 精确计算，附点 ×3/2，连音 ×times/enters）。

- [ ] **Step 1: 写失败测试**

`tests/test_phrase_schema.py`：

```python
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
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_phrase_schema.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'phrase_schema'`

- [ ] **Step 3: 实现 src/phrase_schema.py**

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_phrase_schema.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```powershell
git add src/phrase_schema.py tests/test_phrase_schema.py
git commit -m "feat: 乐句 JSON schema 校验（含小节时值完整性检查）"
```

---

### Task 5: build_gp5.py — JSON → .gp5

**Files:**
- Create: `src/build_gp5.py`
- Test: `tests/test_build_gp5.py`

**Interfaces:**
- Consumes: Task 4 的 `load_phrase`；Task 1 验证过的 PyGuitarPro API 写法。
- Produces: `build_week(json_dir: str, out_path: str, title: str) -> guitarpro.Song`；CLI `python src/build_gp5.py <json_dir> -o output/week09.gp5 --title "..."`。JSON 按文件名排序拼接；每条乐句首小节带 Marker（`label·title ♩=tempo`）和 MixTableChange 速度切换；和弦名写为该小节首拍 BeatText。

- [ ] **Step 1: 写失败测试**

`tests/test_build_gp5.py`：

```python
import json

import guitarpro as gp

from build_gp5 import build_week


def phrase(label: str, tempo: int, fret: int) -> dict:
    return {
        "label": label,
        "title": "测试",
        "tempo": tempo,
        "time_signature": [4, 4],
        "measures": [
            {"chord": "C",
             "beats": [{"duration": 1, "pick": "down",
                        "notes": [{"string": 6, "fret": fret,
                                   "techniques": ["hammer_on"]}]}]}
        ],
    }


def test_build_week_roundtrip(tmp_path):
    d = tmp_path / "json"
    d.mkdir()
    (d / "01_daily.json").write_text(
        json.dumps(phrase("每日必弹", 120, 8)), encoding="utf-8")
    (d / "02_monday.json").write_text(
        json.dumps(phrase("周一", 100, 10)), encoding="utf-8")
    out = tmp_path / "week.gp5"

    build_week(str(d), str(out), "测试周")
    song = gp.parse(str(out))

    measures = song.tracks[0].measures
    assert len(measures) == 2
    assert song.tempo == 120
    assert "每日必弹" in song.measureHeaders[0].marker.title
    assert "周一" in song.measureHeaders[1].marker.title

    b0 = measures[0].voices[0].beats[0]
    assert (b0.notes[0].string, b0.notes[0].value) == (6, 8)
    assert b0.notes[0].effect.hammer is True
    assert b0.effect.pickStroke == gp.BeatStrokeDirection.down
    assert b0.text.value == "C"

    b1 = measures[1].voices[0].beats[0]
    assert b1.effect.mixTableChange.tempo.value == 100
    assert b1.notes[0].value == 10
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_build_gp5.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'build_gp5'`

- [ ] **Step 3: 实现 src/build_gp5.py**

```python
"""把一周的乐句 JSON 构建成单个 .gp5 文件。

用法: python src/build_gp5.py work/json/week09 -o output/week09.gp5 --title "第9周 拨片的跨弦演奏"
JSON 按文件名排序（01_daily.json, 02_monday.json, ...）依次拼接。
"""
import argparse
import pathlib

import guitarpro as gp

from phrase_schema import load_phrase

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
    gp.write(song, out_path)
    return song


def _write_phrase(song: gp.Song, track: gp.Track, phrase: dict, start: int) -> None:
    num, den = phrase["time_signature"]
    for offset, measure_data in enumerate(phrase["measures"]):
        header = song.measureHeaders[start + offset]
        header.timeSignature.numerator = num
        header.timeSignature.denominator.value = den
        if offset == 0:
            header.marker = gp.Marker(
                title=f"{phrase['label']}·{phrase['title']} ♩={phrase['tempo']}")
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
            beat.text = gp.BeatText(value=measure_data["chord"])
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
```

注意：若 Task 1 冒烟测试修正过 API 写法（字段名/构造签名），此处按修正后的写法同步调整。

- [ ] **Step 4: 运行确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_build_gp5.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add src/build_gp5.py tests/test_build_gp5.py
git commit -m "feat: build_gp5.py 由乐句 JSON 构建周 .gp5"
```

---

### Task 6: verify.py — ASCII TAB 回读比对

**Files:**
- Create: `src/verify.py`
- Test: `tests/test_verify.py`

**Interfaces:**
- Consumes: Task 5 的 `build_week`（测试中用它造输入文件）。
- Produces: `ascii_tab(song: guitarpro.Song) -> str`；CLI `python src/verify.py <gp5>` 打印全曲 ASCII TAB。输出格式：每小节一块，第一行时值+拨向（`16v`=十六分下拨、`8^`=八分上拨、附点加 `.`），下面 6 行按弦号排 TAB；连音音符品格加括号、hammer 加 `h`、slide 加 `s`；段落 Marker 单独一行。

- [ ] **Step 1: 写失败测试**

`tests/test_verify.py`：

```python
import json

import guitarpro as gp

from build_gp5 import build_week
from verify import ascii_tab


def test_ascii_tab_shows_marker_frets_and_techniques(tmp_path):
    d = tmp_path / "json"
    d.mkdir()
    (d / "01_monday.json").write_text(json.dumps({
        "label": "周一", "title": "测试", "tempo": 100,
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

    assert "周一" in text          # marker
    assert "Dm" in text            # 和弦名
    assert "10h" in text           # 品格 + hammer 标记
    assert "2v" in text and "2^" in text  # 时值 + 拨向
```

- [ ] **Step 2: 运行确认失败**

Run: `.venv\Scripts\python -m pytest tests/test_verify.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'verify'`

- [ ] **Step 3: 实现 src/verify.py**

```python
"""读回 .gp5 打印 ASCII TAB，供与原书切图逐小节比对。

用法: python src/verify.py output/week09.gp5 [> work/verify_week09.txt]
"""
import argparse

import guitarpro as gp

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
    dur += PICK_ABBR.get(beat.effect.pickStroke, "")
    if beat.status == gp.BeatStatus.rest:
        dur += "r"
    if beat.text:
        dur += f" [{beat.text.value}]"
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
    print(ascii_tab(gp.parse(args.gp5)))


if __name__ == "__main__":
    main()
```

注意：`beat.duration.tuplet.enters` 默认值假设为 1（非连音）；若 Task 1 发现默认 Tuplet 不同，据实调整。

- [ ] **Step 4: 运行确认通过**

Run: `.venv\Scripts\python -m pytest tests/test_verify.py -v`
Expected: PASS

- [ ] **Step 5: 全量回归 + Commit**

Run: `.venv\Scripts\python -m pytest -v`
Expected: 全部通过

```powershell
git add src/verify.py tests/test_verify.py
git commit -m "feat: verify.py 读回 gp5 输出 ASCII TAB"
```

---

### Task 7: 转录第 9 周 7 条乐句（Claude 识谱，人机协作任务）

本任务由主会话中的 Claude 执行（需要视觉读图），不派发给无图子代理。

**Files:**
- Create: `work/json/week09/01_daily.json` … `07_saturday.json`（不入库）

**Interfaces:**
- Consumes: Task 2/3 的 CLI；Task 4 的 schema CLI。
- Produces: 7 个通过 schema 校验的乐句 JSON。

- [ ] **Step 1: 生成切图**

```powershell
.venv\Scripts\python src/render.py "365日！！电吉他手的养成计划.pdf" 20 21 -o work/pages
.venv\Scripts\python src/segment.py work/pages/p020.png work/pages/p021.png -o work/phrases/week09
```

Expected: `work/phrases/week09/` 下 7 组 `system_NN.png` + `system_NN@2x.png`。

- [ ] **Step 2: 逐条识谱**

对每个 `system_NN@2x.png`：用 Read 工具查看图像，**逐小节**转录为 JSON（契约见文首）。文件名与乐句对应：01_daily（每日必弹 ♩=120）、02_monday、03_tuesday、04_wednesday（以上 ♩=100，页 20）、05_thursday、06_friday、07_saturday（♩=100，页 21）。要点：
- 节奏以五线谱行的符尾/符杠为准，TAB 行只提供弦/品。
- 双位数品格与"1 0"两个音的区分：结合上方五线谱音高交叉验证（音高≈弦的空弦音+品数）。
- h./p./s. 弧线记在发起音的 `techniques`；⊓/V 记入 `pick`；`simile` 段落沿用前面的拨序模式。
- 拿不准的音置 `"uncertain": true`，不要猜完就丢。

- [ ] **Step 3: schema 校验**

```powershell
.venv\Scripts\python src/phrase_schema.py work/json/week09/01_daily.json work/json/week09/02_monday.json work/json/week09/03_tuesday.json work/json/week09/04_wednesday.json work/json/week09/05_thursday.json work/json/week09/06_friday.json work/json/week09/07_saturday.json
```

Expected: 7 行 OK。小节时值报错通常意味着漏拍/时值看错——回到对应切图重新核对该小节。

- [ ] **Step 4: 汇总 uncertain 清单**

```powershell
.venv\Scripts\python -c "import json, pathlib; [print(f.name, mi+1, bi+1, n) for f in sorted(pathlib.Path('work/json/week09').glob('*.json')) for mi, m in enumerate(json.loads(f.read_text(encoding='utf-8'))['measures']) for bi, b in enumerate(m['beats']) for n in b.get('notes', []) if n.get('uncertain')]"
```

对每条 uncertain 记录重看 @2x 切图确认或修正，确认后把 `uncertain` 改为 `false`。

（无 commit：`work/` 不入库。）

---

### Task 8: 构建 week09.gp5 并逐小节复核

**Files:**
- Create: `output/week09.gp5`（不入库）
- Create: `work/verify_week09.txt`（不入库）

**Interfaces:**
- Consumes: Task 5/6 的 CLI；Task 7 的 JSON。

- [ ] **Step 1: 构建**

```powershell
.venv\Scripts\python src/build_gp5.py work/json/week09 -o output/week09.gp5 --title "第9周 拨片的跨弦演奏"
```

Expected: `已写入 output/week09.gp5: 28 小节`（7 乐句 × 4 小节；若某乐句实际小节数不同以实谱为准）。

- [ ] **Step 2: 生成 ASCII TAB 并比对**

```powershell
.venv\Scripts\python src/verify.py output/week09.gp5 > work/verify_week09.txt
```

Claude 将 `work/verify_week09.txt` 与 7 张 @2x 切图**逐小节**比对（弦/品/时值/技巧/拨向）。发现差异 → 改对应 JSON → 重跑 Step 1-2，直至一致。

- [ ] **Step 3: 读回完整性断言**

```powershell
.venv\Scripts\python -c "import guitarpro as gp; s = gp.parse('output/week09.gp5'); ms = s.tracks[0].measures; print('measures:', len(ms)); print('markers:', sum(1 for h in s.measureHeaders if h.marker)); assert sum(1 for h in s.measureHeaders if h.marker) == 7"
```

Expected: `markers: 7`，断言通过。

- [ ] **Step 4: Commit（文档级收尾）**

在 `docs/superpowers/specs/2026-07-03-tab2gp-design.md` 的"试点范围"处把"8 条/一页"修正为"7 条/跨两页（周日无谱）"，然后：

```powershell
git add docs
git commit -m "docs: 修正试点范围为 7 条乐句跨两页"
```

---

### Task 9: 用户验收

- [ ] **Step 1: 请用户在 Guitar Pro 中打开 `output/week09.gp5` 验收**

验收标准（来自设计文档）：
1. 文件能打开，7 条乐句齐全，Marker 与各段速度正确；
2. 用户随机抽 2 条乐句对照书页逐音核对，弦/品与节奏无错，技巧记号基本到位；
3. 试听 MIDI 回放与书附 CD 听感一致。

- [ ] **Step 2: 按用户反馈修 JSON 重建，直至验收通过**

验收通过后，试点结束；是否扩展全书批量另立计划。
