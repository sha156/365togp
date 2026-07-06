# 365togp

**谱转 GP5 管线** — 把《365日！！电吉他手的养成计划》扫描页转换为 Guitar Pro 5 (`.gp5`) 文件。

```
render → segment → transcribe → tabcheck → build → verify
```

项目采用**混合管线**：图像处理（render + segment）和文件构建（build + verify + tabcheck）是确定性 Python 代码；中间最关键的"识谱"步骤由人（或具备视觉能力的 LLM）完成，产出的 JSON 再送入 build 阶段。

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

页码 0-based。书的版式：每周跨 2 页（如第 9 周 = 页 20、21）。输出 300dpi PNG 到 `work/pages/`。

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
      "beats": [
        {"duration": 8, "pick": "down", "notes": [{"string": 6, "fret": 0}]},
        ...
      ]
    }
  ]
}
```

每完成一个 JSON 立即校验：

```powershell
.venv\Scripts\python src/phrase_schema.py work/json/week09/*.json
.venv\Scripts\python src/tabcheck.py work/json/week09/*.json
```

详细识谱指南见 [`docs/tab2gp-playbook.md`](docs/tab2gp-playbook.md)。

### 4. build — JSON → .gp5

```powershell
.venv\Scripts\python src/build_gp5.py work/json/week09 -o output/week09.gp5 --title "第9周 基础拨弦"
```

**新功能**：
- **自动分段**：每条乐句末小节后强制换行，段间标双小节线，还原原书排版
- **编码可选**：默认 `cp936`（GBK，GP5 for Windows 最佳）；遇乱码时加 `--encoding utf-8` 或按诊断结果调整

编码诊断：

```powershell
.venv\Scripts\python src/make_diag_gp5.py           # 生成 4 个对照文件
# 在实际软件中打开 output/diag/ 的 A/B/C/D，查明解码方式
```

### 5. verify — 读回校验

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python src/verify.py output/week09.gp5 | Out-File -Encoding utf8 work/verify_week09.txt
```

以 ASCII TAB 形式打印 `.gp5` 内容，供逐小节对比原书切图。

### 6. tabcheck — 乐理弦位校验（新增）

```powershell
# JSON 模式：直接校验识谱产出的 JSON
.venv\Scripts\python src/tabcheck.py work/json/week09/*.json

# Verify 模式：读回 .gp5 再校验
.venv\Scripts\python src/tabcheck.py output/week09.gp5 --verify
```

针对识谱最大的错误源（TAB 数字归弦错误），用乐理做交叉验证：
- **音域检查**：string+fret 组合是否在吉他合理音域（E2~E6）
- **调性检查**：解析标题提取调式（如"C大调"），检测调外音
- **大跳检查**：相邻音跳度超过 2 八度时报警

---

## 项目结构

```
365togp/
├── src/                          # 管线代码
│   ├── render.py                 # PDF → 300dpi PNG
│   ├── segment.py                # PNG → 乐句切图（OpenCV 谱线聚类）
│   ├── phrase_schema.py          # 乐句 JSON schema 定义与校验
│   ├── build_gp5.py              # JSON → .gp5（PyGuitarPro）
│   │     └── lineBreak 强制换行 + hasDoubleBar 双小节线
│   │     └── --encoding 参数支持 cp936 / utf-8 / cp1252
│   ├── tabcheck.py               # 乐理弦位校验（音域/调性/大跳）
│   ├── verify.py                 # .gp5 → ASCII TAB 回读校验
│   └── make_diag_gp5.py          # 编码诊断文件生成器
├── tests/                        # pytest 单元测试（21 例）
├── docs/
│   ├── tab2gp-playbook.md        # 识谱操作手册（含编码诊断章节）
│   └── superpowers/              # 设计文档与规划
├── conftest.py                   # pytest 配置（src 路径注入）
├── requirements.txt
└── .gitignore
```

## 技术要点

- **GP5 编码**：Guitar Pro 5 for Windows 按系统 ANSI 码页解码字符串。默认 `cp936`（GBK）。若遇乱码，用 `make_diag_gp5.py` 诊断解码方式后调整 `--encoding`。
- **换行分段**：GP5 格式原生支持 `lineBreak` 字节，每条乐句强制换行。仅 GP5 原生视图生效；TuxGuitar/alphaTab 忽略该字节但保留 marker 和双小节线。
- **弦位验证**：人手识谱阶段的最大错误源是 TAB 数字归弦错误。`tabcheck.py` 用乐理做四道交叉验证中的前三道（音域/调性/跳度），第 4 道"同构检查"（周一/周二移调验证）按需补全。
- **切图算法**：基于水平投影 + 自适应阈值检测谱线，按线间距聚类为"系统块"，并剔除页眉页脚和右侧表格线。
- **JSON 校验**：`phrase_schema.py` 强制检查每小节时值之和 = 拍号、弦号范围 1-6、品格范围 0-24 等约束。

## License

MIT
