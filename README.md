# 365togp

**谱转 GP5 管线** — 把《365日！！电吉他手的养成计划》扫描页转换为 Guitar Pro 5 (`.gp5`) 文件。

```
render → segment → transcribe(人工/LLM) → build → verify
```

项目采用**混合管线**：图像处理（render + segment + build + verify）是确定性 Python 代码；
中间最关键的"识谱"步骤由人（或具备视觉能力的 LLM）完成，产出的 JSON 再送入 build 阶段。

最终产物是可以直接导入 Guitar Pro / TuxGuitar 播放、变速、循环练习的 `.gp5` 文件。

---

## 管线步骤

### 0. 环境准备

```powershell
# Python 3.11+，推荐 venv
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

依赖：`pymupdf`（PDF 渲染）、`opencv-python`（图像切分）、`numpy`、`PyGuitarPro`（GP5 读写）、`pytest`。

### 1. render — PDF 页 → 300dpi PNG

```powershell
.venv\Scripts\python src/render.py "365日！！电吉他手的养成计划.pdf" <页码...> -o work/pages
```

页码 0-based。书的结构是每周跨 2 页（如第 9 周 = 页 20、21）。输出 300dpi PNG 到 `work/pages/`。

### 2. segment — 整页 → 每条乐句切图

```powershell
.venv\Scripts\python src/segment.py work/pages/p020.png work/pages/p021.png -o work/phrases/week09
```

通过谱线聚类自动定位并裁出每条练习乐句（五线谱 + TAB 系统块）。输出 `system_NN.png` 与 `system_NN@2x.png`。

**关键**：输出后必须目检每张切图，确保标题栏、五线谱、TAB、指法行完整。

### 3. transcribe — 识谱 → 乐句 JSON（核心，人/LLM 完成）

参考输出后的切图，逐小节读取音高、节奏、技巧、拨向，按以下 JSON 格式记录：

```json
{
  "label": "每日必弹",
  "title": "C大调音阶（Ｇ型）",
  "tempo": 90,
  "time_signature": [4, 4],
  "measures": [
    {
      "barline": "regular",
      "notes": [
        [0, 8, "down"], [2, 8, "down"], [3, 8, "down"], ...
      ]
    }
  ]
}
```

每完成一个 JSON 立即校验：

```powershell
.venv\Scripts\python src/phrase_schema.py work/json/week09/*.json
```

详细识谱指南见 [`docs/tab2gp-playbook.md`](docs/tab2gp-playbook.md)。

### 4. build — JSON → .gp5

```powershell
.venv\Scripts\python src/build_gp5.py work/json/week09 -o output/week09.gp5 --title "第9周 基础拨弦"
```

JSON 按文件名排序后依次拼接为同一 `.gp5` 的多个 Track（或小节）。编码固定 `cp936`（GBK），
确保 Guitar Pro for Windows 正确显示中文标题和 Marker。

### 5. verify — 读回校验

```powershell
.venv\Scripts\python src/verify.py output/week09.gp5
```

以 ASCII TAB 形式打印 `.gp5` 内容，供逐小节对比原书切图，确认音高、节奏、技巧无误。

---

## 项目结构

```
365togp/
├── src/                  # 管线代码
│   ├── render.py         # PDF → 300dpi PNG
│   ├── segment.py        # PNG → 乐句切图（OpenCV 谱线聚类）
│   ├── phrase_schema.py  # 乐句 JSON schema 定义与校验
│   ├── build_gp5.py      # JSON → .gp5（PyGuitarPro）
│   └── verify.py         # .gp5 → ASCII TAB 回读校验
├── tests/                # pytest 单元测试
├── docs/
│   ├── tab2gp-playbook.md       # 识谱操作手册
│   └── superpowers/              # 设计文档与规划
├── conftest.py           # pytest 配置（src 路径注入）
├── requirements.txt
└── .gitignore
```

## 技术要点

- **GP5 编码**：Guitar Pro 5 for Windows 按系统 ANSI 码页解码字符串。项目统一用 `cp936`（GBK）读写，确保中文标题 / Marker 正常显示。
- **切图算法**：基于水平投影 + 自适应阈值检测谱线，按线间距聚类为"系统块"，并剔除页眉页脚和右侧表格线。
- **JSON 校验**：`phrase_schema.py` 强制检查每小节时值之和 = 拍号、弦号范围 1-6、品格范围 0-24 等约束。

## License

MIT
