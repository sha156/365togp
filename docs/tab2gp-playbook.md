# tab2gp 识谱转换操作手册（模型无关）

> 目标读者：任何具备视觉能力的 LLM（Sonnet / Opus / 其他）。
> 按本手册逐步执行，即可把《365日！！电吉他手的养成计划》扫描页转成 Guitar Pro `.gp5`。
> 管线代码是确定性的，模型只负责第 3 步"识谱"；其余步骤全部是跑命令。

## 环境

- 一律使用 `.venv\Scripts\python`（Python 3.11 venv）。依赖见 `requirements.txt`。
- 源 PDF：`365日！！电吉他手的养成计划.pdf`（仓库根目录）。
- 中间产物在 `work/`，成品在 `output/`，均不入库。

## 五段管线

```
render → segment → transcribe(模型视觉) → build → verify
```

### 1. render：PDF 页 → 300dpi PNG

```powershell
.venv\Scripts\python src/render.py "365日！！电吉他手的养成计划.pdf" <页码...> -o work/pages
```

页码 0-based。书的版式：每周跨 2 页（如第 9 周 = 页 20、21）。

### 2. segment：整页 → 每条乐句切图

```powershell
.venv\Scripts\python src/segment.py work/pages/pNNN.png ... -o work/phrases/weekNN
```

输出 `system_NN.png` 与 `system_NN@2x.png`。**必须目检每张切图**：标题栏、五线谱、
TAB、指法行要完整。数量对≠切对（曾出现数量碰巧对但边界错位的 bug）。

### 3. transcribe：识谱 → 乐句 JSON（模型的核心工作）

产出 `work/json/weekNN/NN_<slug>.json`，契约见
`docs/superpowers/plans/2026-07-03-tab2gp-pilot.md`"乐句 JSON 契约"。

**铁律：绝不整条读谱。** 整条系统图约 8000px 宽，压缩显示后数字不可读。流程：

1. **先读整页**拿上下文：每条乐句的 label（每日必弹/周一…）、标题、♩=速度、CD 时间、和弦名。
2. **逐小节裁剪放大 TAB 区**（3~4 倍），用 OpenCV 临时脚本切竖条或定向 crop：
   一条系统 4 小节 → 至少 4 张放大图；节奏复杂的小节（滑弦/勾弦/十六分）单独再放大。
3. **弦位判定是最大错误源**（试点中唯一被用户验收打回的问题就是它）。
   TAB 数字行距极密，判定一个数字在第几弦必须同时过四道交叉验证：
   - **线位**：数字中心对齐 6 条线中的哪一条（放大到能数清线再下结论）；
   - **指法行**（食/中/名/小）：同一把位内 食=最低品、小=最高品，能反推品格但**不能**区分弦；
   - **五线谱音高**：弦的空弦音+品数 ≈ 谱面音高（6弦E2、5弦A2、4弦D3、3弦G3、2弦B3、1弦E4），
     音高高度对不上就是弦错了；
   - **音乐逻辑**：这本书的练习都是音阶/琶音套路（如 C 大调音阶弧线、和弦分解同构移位）。
     转出来的旋律若出现无端大跳或调外音，优先怀疑弦位/品格读错。
   四者矛盾时：**以线位+五线谱音高为准**，指法与套路做旁证。
4. **节奏**以五线谱行的符杠为准（TAB 行只给弦/品）。注意本书常见"14 个十六分 + 结尾八分"
   的 15 音小节。拨向 ⊓=down、V=up；滑弦(s.)/勾弦(p.)的目标音无拨向记号。
5. **同构小节用脚本生成** JSON（如周一/周二的四小节只是移调），减少手抄错误。
6. 拿不准的音写 `"uncertain": true`，之后统一复核，禁止猜完就丢。

每写完一个 JSON 立即校验（会强制检查每小节时值之和=拍号）：

```powershell
.venv\Scripts\python src/phrase_schema.py work/json/weekNN/*.json
```

然后跑**乐理弦位校验**（检测调外音、不合理大跳等可能的口误）：

```powershell
.venv\Scripts\python src/tabcheck.py work/json/weekNN/*.json
```

tabcheck 使用四道交叉验证法（音域/调性/间隔跳度），输出 MEDIUM 及以上建议需人工复核。

### 4. build：JSON → .gp5

```powershell
.venv\Scripts\python src/build_gp5.py work/json/weekNN -o output/weekNN.gp5 --title "第N周 xxx"
```

编码默认 cp936（中文 Windows 的 Guitar Pro 按系统码页读字符串，中文 Marker 才能正常显示）。

如果打开后中文乱码，用诊断包判定解码方式（详见"编码诊断"章节），然后按需加 `--encoding` 参数：

```powershell
# cp936 适用于 GP5 / 中文 Windows 系统码页
# utf-8  适用于 alphaTab / TuxGuitar 新版默认
.venv\Scripts\python src/build_gp5.py work/json/weekNN -o output/weekNN.gp5 --title "第N周 xxx" --encoding utf-8
```

### 4.5 编码诊断（首次使用或遇到乱码时）

乱码通常是**读取软件的解码方式**问题（非写入缺陷）。已生成诊断包 `output/diag/`：

| 文件 | 编码 | marker 内容 |
|---|---|---|
| A_ascii.gp5 | ascii | `A-ASCII: plain marker`（对照组） |
| B_gbk.gp5 | cp936 | `B-GBK: 每日必弹②→Ｇ` |
| C_utf8.gp5 | utf-8 | `C-UTF8: 每日必弹②→Ｇ` |
| D_cp1252.gp5 | cp1252 | `D-CP1252: Café déjà vu` |

**在用户的实际软件里打开四个文件，看哪个 marker 显示正常：**

| 正常文件 | 结论 | 对策 |
|---|---|---|
| B | 软件按 GBK/系统 ANSI 解码 | 维持 cp936 不变 |
| C | 软件按 UTF-8 解码 | build_gp5 加 `--encoding utf-8` |
| D | 固定 cp1252（GP6/7/8） | marker 改双语 ASCII 前缀 |
| **全部（含 A 纯 ASCII 也乱）** | **问题不在编码，是软件按扩展名分派解析器** | 见下方"扩展名陷阱" |

**扩展名陷阱（2026-07-07 实测发现）**：若连 `A_ascii.gp5`（无中文、任何码页都不该乱）也显示异常，
说明问题根本不是字符编码，而是目标软件看到 `.gp5` 后缀时走了错的/过时的解析分支。
`output/diag/*.gp`（与同名 `.gp5` **字节完全相同**，仅扩展名不同）已生成并加入验证：
用 `cmp A_ascii.gp5 A_ascii.gp` 可确认二者一致。PyGuitarPro 读文件版本号是从文件头
`FICHIER GUITAR PRO vX.XX` 字符串解析的，与文件名后缀无关（`guessVersionByExtension`
只在写入且未显式指定 version 时才查后缀，且 `.gp` 这种未知后缀会直接 fallback 到
gp5 (5,1,0)，内容不变）——**如果用户在实际软件里打开同一份内容的 `.gp5` 乱码而 `.gp` 正常，
根因 100% 在阅读软件那一侧的扩展名分派逻辑，不是本项目的编码参数**。
可行对策：`build_gp5.py -o` 的输出路径直接用 `.gp` 后缀（内容仍是标准 GP5 v5.10 二进制，
`verify.py`/`gp.parse` 完全不受影响），不需要改任何代码。

### 5. verify：读回比对（模型的第二道工作）

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python src/verify.py output/weekNN.gp5 | Out-File -Encoding utf8 work/verify_weekNN.txt
```

把 ASCII TAB 与第 3 步的放大切图**逐小节**比对（弦/品/时值/技巧/拨向）。
发现差异→改 JSON→重跑 build+verify，直至一致。最后完整性断言：

```powershell
.venv\Scripts\python -c "import guitarpro as gp; s=gp.parse('output/weekNN.gp5', encoding='cp936'); assert sum(1 for h in s.measureHeaders if h.marker)==<乐句数>"
```

### 6. 用户验收

Guitar Pro 打开：Marker/速度齐全 → 抽查逐音对照 → MIDI 回放与书附 CD 对比听感。
**试听是最强的最终防线**：弦位错一根，音高差纯四度，耳朵立刻能听出来。

## 已踩过的坑（换模型必读）

| 坑 | 现象 | 对策 |
|---|---|---|
| 整条图直接读 | 数字全糊 | 逐小节 crop+放大，没有例外 |
| 弦位归行错误 | 音高差一根弦（纯四度） | 上面的四道交叉验证 |
| segment 边界错位 | 切图数量对但内容切半 | 每张切图目检完整性 |
| gp5 编码 | 中文 Marker 写入报 UnicodeEncodeError | 读写统一 `encoding="cp936"` |
| 15 音小节 | 时值校验报"时值之和≠拍号" | 末音是八分不是十六分 |
| 双位数 vs 两个音 | "10"读成"1 0" | 用五线谱音高交叉验证 |

## 确定性 CV 识读（实验，2026-07-08）

`src/tab_reader.py` + `src/reconcile.py` 是"确定性 CV 主读 + 机械对账"的实现，目标是把
LLM 视觉识谱的三大错误源（弦位归行/双位数拆分/音序）换成确定性算法。

**管线**：粗旋正（书扫描斜约 0.5°）→ 局部窗口两遍共识锁定 TAB 六线（防误锁五线谱）→
分段线位插值（抗书脊侧弯曲）→ 带内局部 Otsu → **胜者通吃 NCC 模板匹配**（模板=书内自体
数字字模，`work/templates/`，不入库）→ 数字墨迹质心定弦。

```powershell
.venv\Scripts\python src/tab_reader.py work/phrases/weekNN/system_XX.png --templates work/templates/week9
.venv\Scripts\python src/reconcile.py <切图> <乐句json> --templates work/templates/week9
```

reconcile 把检测与 JSON 逐音对账（Needleman-Wunsch 对齐），判定 OK/弦错/品错/漏检(hole)/
低分，任一非 OK 进复核清单——**这是"零静默错误"的落点**。

**已验证**：模板全覆盖的 system_01（品 7-10）达 32/32 弦位+品格全对、0 静默错误
（`tests/test_tab_reader.py` 锁定）。真命中分 ≥0.73、误配 ≤0.65，置信度天然分层。

**当前限制（下一步）**：
- **模板库不全是最大瓶颈**：干净字模只齐了 7/8/9/10；6/13/15/17 是粗样、5/14/16 缺。
  缺模板→漏检(hole)（安全，会标红）；**粗模板→品错**（f6 在 sys01 的"8"上误判成"6"，但被
  reconcile 逮住，非静默）。手工凑模板极慢，是待解工程点。
- 缺模板会让 NW 对齐**级联错位**（sys05 缺"5"模板→下游 27 处伪"弦错"）。所以扩库要
  先补全再谈准确率。**教训重申：缺类比低分更危险。**
- 连通域分割数字是死路（符干粘数字头顶）；自适应阈值在半调网纹底上会整体反相——都别再试。
