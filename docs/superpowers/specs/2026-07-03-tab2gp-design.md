# 设计文档：365日 TAB 谱 → Guitar Pro 转换器（tab2gp）

日期：2026-07-03
状态：已确认（试点阶段）

## 背景与目标

《365日！！电吉他手的养成计划》是一本纯扫描版 PDF（110 页、每页一张整页图、无文字层）。
全书以"周"为单位组织：每页一周，含 1 条"每日必弹"乐句 + 周一至周日各 1 条乐句，
每条乐句为"五线谱 + TAB"双行谱，带速度、和弦名、拨序（⊓/V）、滑弦/勾弦/锤弦等记号。

目标：把书中练习乐句转换成 Guitar Pro 可直接打开的谱文件，供用户**个人练习**使用（不对外分发）。

**试点范围**：书页 22（PDF 第 21 页，0-based index 20）"第 9 周 拨片的跨弦演奏"，共 8 条乐句。
跑通全流程并经用户在 Guitar Pro 中验收后，再扩展为全书批量流程。

## 已确认的决策

| 决策点 | 结论 |
|--------|------|
| 识谱方式 | 混合：CV 自动切图定位 + Claude 视觉识谱 |
| 试点范围 | 先做一周（一页），验收后再谈批量 |
| 文件组织 | 每周一个 .gp5，8 条乐句各占一段，带 Marker 与各自速度 |
| 输出格式 | .gp5（PyGuitarPro 上限；GP7/8 可直接打开）。如需新版 .gp 容器，后续评估 slundi/guitarpro（Rust）或用 GP8 批量另存 |
| Python 环境 | 统一 `py -3.11` + venv（本机默认 python 是 3.9） |

## 整体架构（五段管线）

```
PDF ──render──▶ 整页PNG(300dpi) ──segment──▶ 单条乐句切图 ──transcribe──▶ JSON ──build──▶ .gp5 ──verify──▶ 验收
     PyMuPDF          OpenCV 水平投影定位谱表       Claude 视觉识谱      PyGuitarPro      读回校验 + ASCII TAB 对照
```

核心思路：**JSON 是人可校对的中间层**。识谱错误只改 JSON 后重新 build，不动代码；
将最不可靠的一环（识谱）与确定性的一环（写 gp5）解耦。

## 各阶段职责

### 1. render（src/render.py）
- 输入：PDF 路径 + 页码；输出：`work/pages/pXXX.png`（300dpi）。
- 依赖 PyMuPDF。

### 2. segment（src/segment.py）
- 对整页 PNG 做水平投影 / 行检测，定位每个"五线谱 + TAB"系统块。
- 输出：`work/phrases/week09/NN_<label>.png`（每条乐句一张切图，另存 2x 放大版供识谱）。
- 试点阶段允许辅以人工微调裁切参数；全自动鲁棒性留给批量阶段强化。

### 3. transcribe（Claude 视觉识谱）
- Claude 逐条读切图（逐小节转录），输出 `work/json/week09/NN_<label>.json`。
- JSON schema（单条乐句）：

```json
{
  "label": "monday",
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
          "notes": [{"string": 3, "fret": 10}],
          "techniques": [],
          "pick": "down",
          "tied": false,
          "uncertain": false
        }
      ]
    }
  ]
}
```

- `duration`：1/2/4/8/16/32（GP 时值语义）；`string`：1=最细弦；
  `techniques`：`slide` / `pull_off` / `hammer_on`；`pick`：`down`（⊓）/ `up`（V）/ 省略。
- 识谱拿不准的音符置 `uncertain: true`，汇总为人工复核清单。

### 4. build（src/build_gp5.py）
- 读入一周全部 JSON → 生成 `output/week09.gp5`。
- 单轨电吉他（标准调弦、失真音色），每条乐句一段：段首 Marker（"每日必弹"/"周一"…）、
  MixTableChange 设置该段速度；和弦名写为 beat text；技巧与拨序映射到 gp5 原生效果。
- 乐句之间不共享小节；直接顺序排列。

### 5. verify（src/verify.py）
- 用 PyGuitarPro 读回生成的 .gp5，打印 ASCII TAB（含时值与技巧标记）。
- Claude 将 ASCII TAB 与原切图逐小节比对，修正 JSON 后重新 build。
- 最终由用户在 Guitar Pro 中人工验收（试听 + 对照书页）。

## 转录范围（第一版）

- ✅ 音符（弦/品）、时值（含附点、连音线）、拍号、速度、和弦名（小节文本）
- ✅ 技巧：滑弦(s.)、勾弦(p.)、锤弦(h.)、拨片方向 ⊓/V
- ❌ 不做：左手指法标注（中/食/小）、书中文字说明、CD 音轨对齐

## 目录结构

```
365togp/
├── docs/superpowers/specs/   # 本文档与实施计划
├── src/                      # render.py / segment.py / build_gp5.py / verify.py
├── work/                     # pages/ phrases/ json/（中间产物，按周分目录，git 忽略大图）
├── output/                   # week09.gp5
├── requirements.txt          # pymupdf, opencv-python, pyguitarpro
└── 365日！！电吉他手的养成计划.pdf（源文件，git 忽略）
```

## 风险与对策

| 风险 | 对策 |
|------|------|
| 识谱准确率（双位数品格密集、扫描质量一般） | 300dpi 渲染 + 切图 2x 放大 + 逐小节转录 + verify 阶段 ASCII TAB 对照 + uncertain 标记人工复核 |
| PyGuitarPro 时值/技巧映射细节（连音线、附点、pick stroke 字段名） | build 前先写最小冒烟脚本验证往返读写 |
| segment 对不同版式页面不鲁棒 | 试点只需对这一页可用；批量阶段再泛化 |
| 版权 | 产出仅个人练习使用，不对外分发、不入公开仓库 |

## 验收标准（试点）

1. `output/week09.gp5` 能在 Guitar Pro 中打开，8 条乐句齐全、Marker 与速度正确。
2. 随机抽 2 条乐句逐音对照书页，音高（弦/品）与节奏无错；技巧记号基本到位。
3. 全流程（render→verify）可用命令复跑。
