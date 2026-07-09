"""确定性 TAB 六线谱识读：扫描页系统块 → (弦, 品, x, 置信度) 检测序列。

管线：粗旋正 → 分段线位拟合（抗页面弯曲）→ 带内局部 Otsu →
胜者通吃 NCC 模板匹配（模板=书内自体字模）→ 最近线归弦。
低置信/未匹配位置留给 reconcile 标红，不臆测。

用法: python src/tab_reader.py <system.png> --templates work/templates/week9
"""
import argparse
import pathlib

import cv2
import numpy as np

# 300dpi 扫描页经验参数（gap=TAB 相邻线间距，运行时实测）
_WIN_STEP = 80
_WIN_HALF = 20
_LINE_FILL = 0.7          # 采样窗内某行被判为谱线的填充率
_LINE_THICK = 7           # 谱线最大厚度(px)
_NCC_THRESH = 0.70        # NCC 命中阈值（真命中≥0.73、误配≤0.65，实测可分层）
_LOWCONF = 0.80           # 低于此分标记 low_conf 供复核


def cluster_1d(vals, max_gap):
    """升序序列按间隔聚类，返回 [(min, max), ...]。"""
    out = []
    start = prev = vals[0]
    for v in vals[1:]:
        if v - prev > max_gap:
            out.append((start, prev))
            start = v
        prev = v
    out.append((start, prev))
    return out


def _window_groups(bw, W):
    """每个 x 窗口找出所有等距 6 线候选组。"""
    per_window = []
    for x in range(150, W - 150, _WIN_STEP):
        win = bw[:, x - _WIN_HALF:x + _WIN_HALF]
        rowfill = win.sum(axis=1) / 255.0 / (2 * _WIN_HALF)
        rows = np.where(rowfill > _LINE_FILL)[0]
        if len(rows) == 0:
            continue
        centers = sorted((a + b) / 2 for a, b in cluster_1d(list(rows), 2)
                         if (b - a) <= _LINE_THICK)
        groups = [centers[i:i + 6] for i in range(len(centers) - 5)
                  if (lambda d: d.max() - d.min() <= 5 and 12 <= np.median(d) <= 60)
                  (np.diff(centers[i:i + 6]))]
        if groups:
            per_window.append((x, groups))
    return per_window


def sample_tab_lines(bw, W):
    """两遍共识锁定同一条 TAB 带：先估全局中心，再每窗选最近组。"""
    per_window = _window_groups(bw, W)
    if len(per_window) < 5:
        raise RuntimeError(f"只有 {len(per_window)} 个窗口检出 6 线组")
    tab_y = float(np.median([max(np.median(g) for g in gs)
                             for _, gs in per_window]))
    hits = {i: [] for i in range(6)}
    for x, groups in per_window:
        best = min(groups, key=lambda g: abs(np.median(g) - tab_y))
        if abs(np.median(best) - tab_y) > 60:
            continue
        for k in range(6):
            hits[k].append((x, best[k]))
    if len(hits[0]) < 5:
        raise RuntimeError(f"共识后仅剩 {len(hits[0])} 个窗口")
    gap = float(np.median([hits[k + 1][i][1] - hits[k][i][1]
                           for k in range(5) for i in range(len(hits[0]))]))
    return hits, gap


def piecewise_profiles(hits, W):
    """逐线用采样点做分段线性插值 → profiles (6, W)，抗弯曲。"""
    idx = np.arange(W)
    profiles = []
    for k in range(6):
        pts = sorted(hits[k])
        xs = np.array([p[0] for p in pts], float)
        ys = np.array([p[1] for p in pts], float)
        profiles.append(np.interp(idx, xs, ys))
    return np.array(profiles)


def deskew_and_profile(gray):
    """粗旋正 + 分段线位拟合。返回 (旋正灰度, profiles, gap, 角度)。"""
    H, W = gray.shape
    _, bw0 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    hits, _ = sample_tab_lines(bw0, W)
    pts = sorted(hits[0])
    xs = np.array([p[0] for p in pts], float)
    ys = np.array([p[1] for p in pts], float)
    angle = float(np.degrees(np.arctan(np.polyfit(xs, ys, 1)[0])))
    M = cv2.getRotationMatrix2D((W / 2, H / 2), angle, 1.0)
    gray2 = cv2.warpAffine(gray, M, (W, H), flags=cv2.INTER_CUBIC, borderValue=255)
    blur = cv2.medianBlur(gray2, 3)
    _, bw = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    hits2, gap = sample_tab_lines(bw, W)
    return gray2, piecewise_profiles(hits2, W), gap, angle


def load_templates(templates_dir):
    """加载模板库 {品格: [模板图]}，文件名 f<品格>_*.png。"""
    bank = {}
    for p in sorted(pathlib.Path(templates_dir).glob("f*.png")):
        fret = int(p.stem.split("_")[0][1:])
        bank.setdefault(fret, []).append(cv2.imread(str(p), cv2.IMREAD_GRAYSCALE))
    if not bank:
        raise RuntimeError(f"{templates_dir} 下无模板")
    return bank


def _band_bounds(profiles, gap):
    y0 = int(profiles[0].min() - gap * 1.0)
    y1 = int(profiles[-1].max() + gap * 1.0)
    return max(0, y0), y1


def detect(gray2, profiles, gap, bank, thresh=_NCC_THRESH, x_min=300):
    """胜者通吃 NCC：每模板算响应 → 按数字中心散射取 max → 峰值 NMS。

    每个位置输出一个检测（其最佳品格），避免多模板重复检出。
    """
    W = gray2.shape[1]
    y0, y1 = _band_bounds(profiles, gap)
    band = gray2[y0:y1, :]
    H = band.shape[0]
    best = np.full((H, W), -1.0, np.float32)
    bfret = np.full((H, W), -1, np.int32)
    bw_ = np.zeros((H, W), np.int32)
    bh_ = np.zeros((H, W), np.int32)
    for fret, tpls in bank.items():
        for tpl in tpls:
            th, tw = tpl.shape
            if th >= H or tw >= W:
                continue
            res = cv2.matchTemplate(band, tpl, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.mgrid[0:res.shape[0], 0:res.shape[1]]
            cy, cx = ys + th // 2, xs + tw // 2
            upd = res > best[cy, cx]
            best[cy[upd], cx[upd]] = res[upd]
            bfret[cy[upd], cx[upd]] = fret
            bw_[cy[upd], cx[upd]] = tw
            bh_[cy[upd], cx[upd]] = th
    ys, xs = np.where(best >= thresh)
    cand = sorted(zip(best[ys, xs], ys, xs), key=lambda t: -t[0])
    picked = []
    for sc, y, x in cand:
        if x < x_min:
            continue
        # 同弦重叠去重：真单音一拍一个（间距≥两位数宽），故同弦 <1.3gap 内的
        # 低分检测必为交叉模板幻影（如"14"误配"10"的左半），抑制之。
        if any(abs(x - px) < gap * 1.3 and abs(y - py) < gap * 0.7
               for _, py, px in picked):
            continue
        picked.append((sc, y, x))
    det = []
    for sc, y, x in sorted(picked, key=lambda t: t[2]):
        tw, th = int(bw_[y, x]), int(bh_[y, x])
        yf = y + y0
        # 用数字真实墨迹质心定弦，而非模板中心（模板含线残端会偏低）
        cy_ink = _ink_centroid_y(band, x, y, tw, gap, y0)
        xi = int(np.clip(x, 0, W - 1))
        d = np.abs(profiles[:, xi] - cy_ink)
        det.append(dict(fret=int(bfret[y, x]), string=int(np.argmin(d)) + 1,
                        cx=float(x), cy=float(cy_ink), score=float(sc),
                        w=tw, h=th, line_diff=float(d.min()),
                        low_conf=bool(sc < _LOWCONF)))
    return det


def _ink_centroid_y(band, cx, cy, tw, gap, y0):
    """在匹配框附近取数字墨迹的竖向质心（全图坐标），去横线偏置。"""
    H, W = band.shape
    x0 = max(0, int(cx - tw / 2) - 1)
    x1 = min(W, int(cx + tw / 2) + 1)
    y_lo = max(0, int(cy - gap * 0.9))
    y_hi = min(H, int(cy + gap * 0.9))
    win = band[y_lo:y_hi, x0:x1]
    _, bw = cv2.threshold(win, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    # 去贯穿窗宽的横线（谱线），只留数字笔画
    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, int(tw * 0.8)), 1))
    bw = cv2.bitwise_and(bw, cv2.bitwise_not(cv2.morphologyEx(bw, cv2.MORPH_OPEN, hk)))
    ys, _ = np.where(bw > 0)
    if len(ys) < 3:
        return float(cy)
    return float(y_lo + np.median(ys) + y0)


def read_system(png_path, templates_dir):
    """识读一个系统块，返回 {detections, gap, skew}。"""
    gray = cv2.imread(str(png_path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        raise ValueError(f"无法读取 {png_path}")
    gray2, profiles, gap, angle = deskew_and_profile(gray)
    bank = load_templates(templates_dir)
    det = detect(gray2, profiles, gap, bank)
    return {"detections": det, "gap": gap, "skew": angle,
            "covered_frets": sorted(bank)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("png")
    ap.add_argument("--templates", required=True)
    args = ap.parse_args()
    r = read_system(args.png, args.templates)
    print(f"gap={r['gap']:.1f} skew={r['skew']:.3f} "
          f"覆盖品格={r['covered_frets']} 检测数={len(r['detections'])}")
    for i, d in enumerate(r["detections"], 1):
        flag = " [低分]" if d["low_conf"] else ""
        print(f"{i:3d} x={d['cx']:6.0f} 弦{d['string']} 品{d['fret']:2d} "
              f"分={d['score']:.2f}{flag}")


if __name__ == "__main__":
    main()
