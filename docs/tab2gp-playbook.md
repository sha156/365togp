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

### 4. build：JSON → .gp5

```powershell
.venv\Scripts\python src/build_gp5.py work/json/weekNN -o output/weekNN.gp5 --title "第N周 xxx"
```

编码固定 cp936（中文 Windows 的 Guitar Pro 按系统码页读字符串，中文 Marker 才能正常显示）。

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
