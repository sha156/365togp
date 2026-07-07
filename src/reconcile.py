"""三道防线之一：把 CV 识读结果与现有乐句 JSON 逐音机械对账。

对齐用 Needleman-Wunsch（按品格序列），逐音判定：
  OK / 弦错 / 品错 / 漏检(hole) / 多检 / 低分。
任一非 OK 进人工复核清单——这是"零静默错误"的落点。

用法: python src/reconcile.py <system.png> <phrase.json> --templates work/templates/week9
"""
import argparse
import json
import pathlib

import numpy as np

from tab_reader import read_system


def gt_notes(json_path):
    """展开乐句 JSON 为有序音符 [(measure, string, fret, uncertain)]。"""
    data = json.loads(pathlib.Path(json_path).read_text(encoding="utf-8"))
    out = []
    for mi, m in enumerate(data["measures"], 1):
        for b in m["beats"]:
            for n in b.get("notes", []):
                out.append((mi, n["string"], n["fret"], bool(n.get("uncertain"))))
    return out


def align(a, b):
    """Needleman-Wunsch 对齐两序列（相等+2/不等-1/空位-1），返回对齐路径。

    路径元素: (i, j) 表示 a[i]↔b[j]，(i, None) a 多出，(None, j) b 多出。
    """
    n, m = len(a), len(b)
    dp = np.zeros((n + 1, m + 1))
    for i in range(1, n + 1):
        dp[i][0] = -i
    for j in range(1, m + 1):
        dp[0][j] = -j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            sc = 2 if a[i - 1] == b[j - 1] else -1
            dp[i][j] = max(dp[i - 1][j - 1] + sc, dp[i - 1][j] - 1, dp[i][j - 1] - 1)
    i, j, path = n, m, []
    while i > 0 or j > 0:
        if i > 0 and j > 0 and dp[i][j] == dp[i - 1][j - 1] + (2 if a[i - 1] == b[j - 1] else -1):
            path.append((i - 1, j - 1)); i, j = i - 1, j - 1
        elif i > 0 and dp[i][j] == dp[i - 1][j] - 1:
            path.append((i - 1, None)); i -= 1
        else:
            path.append((None, j - 1)); j -= 1
    return path[::-1]


def reconcile(png_path, json_path, templates_dir):
    """对账并返回 {rows, summary}。rows 逐 GT 音一条，附 CV 判定。"""
    r = read_system(png_path, templates_dir)
    det = r["detections"]
    gt = gt_notes(json_path)
    covered = set(r["covered_frets"])
    # 用 (弦,品) 做对齐键
    path = align([(d["string"], d["fret"]) for d in det],
                 [(s, f) for _, s, f, _ in gt])
    rows, review = [], []
    counts = dict(ok=0, string=0, fret=0, hole=0, extra=0, low=0)
    for di, gi in path:
        if gi is None:
            d = det[di]
            rows.append(dict(kind="多检", cv=f"弦{d['string']}品{d['fret']}",
                             x=d["cx"], score=d["score"]))
            counts["extra"] += 1
            review.append(rows[-1])
            continue
        mi, s, f, unc = gt[gi]
        if di is None:
            kind = "漏检(hole)" if f in covered else f"漏检-无模板(品{f})"
            rows.append(dict(kind=kind, measure=mi, gt=f"弦{s}品{f}", cv="-"))
            counts["hole"] += 1
            review.append(rows[-1])
            continue
        d = det[di]
        cv = f"弦{d['string']}品{d['fret']}"
        gts = f"弦{s}品{f}"
        if d["string"] == s and d["fret"] == f:
            if d["low_conf"]:
                rows.append(dict(kind="低分OK", measure=mi, gt=gts, cv=cv,
                                 score=d["score"]))
                counts["low"] += 1
                review.append(rows[-1])
            else:
                rows.append(dict(kind="OK", measure=mi, gt=gts, cv=cv,
                                 score=d["score"]))
                counts["ok"] += 1
        else:
            kind = "弦错" if d["fret"] == f else ("品错" if d["string"] == s else "全错")
            rows.append(dict(kind=kind, measure=mi, gt=gts, cv=cv,
                             score=d["score"]))
            counts["string" if d["string"] != s else "fret"] += 1
            review.append(rows[-1])
    summary = dict(gt=len(gt), det=len(det), **counts,
                   accuracy=counts["ok"] / len(gt) if gt else 0.0,
                   covered=sorted(covered))
    return dict(rows=rows, review=review, summary=summary, meta=r)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("png")
    ap.add_argument("json")
    ap.add_argument("--templates", required=True)
    ap.add_argument("--all", action="store_true", help="打印全部逐音行(默认只打印复核项)")
    args = ap.parse_args()
    res = reconcile(args.png, args.json, args.templates)
    s = res["summary"]
    print(f"GT={s['gt']} 检测={s['det']} 覆盖品格={s['covered']} "
          f"gap={res['meta']['gap']:.1f}")
    print(f"OK={s['ok']} 弦错={s['string']} 品错={s['fret']} "
          f"漏检={s['hole']} 多检={s['extra']} 低分OK={s['low']} "
          f"→ 全绿准确率={s['accuracy']*100:.1f}%")
    rows = res["rows"] if args.all else res["review"]
    if rows:
        print(f"\n--- {'全部' if args.all else '需复核'} {len(rows)} 项 ---")
        for r in rows:
            extra = " ".join(f"{k}={v}" for k, v in r.items() if k != "kind")
            print(f"  [{r['kind']}] {extra}")


if __name__ == "__main__":
    main()
