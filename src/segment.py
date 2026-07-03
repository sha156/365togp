"""从整页 PNG 中定位并裁出每条乐句（五线谱+TAB 系统块）。

用法: python src/segment.py <page.png...> -o work/phrases/week09
"""
import argparse
import pathlib

import cv2
import numpy as np

# 针对 300dpi 扫描页的经验参数（自适应阈值 + 宽间距聚类）
MIN_LINE_WIDTH_RATIO = 0.10  # 谱线横贯页宽比例（自适应阈值下可更宽容）
LINE_GAP = 4                  # 行聚类间隔（px）
SYSTEM_GAP = 240              # 系统聚类间隔：块内中心距<=207px，块间>=290px
MIN_LINES_PER_SYSTEM = 7      # 一个系统至少 7 个行簇（5+6=11 容忍漏检）
MAX_X_START_RATIO = 0.30      # 谱线/标题条均起于左缘；右侧表格线据此剔除
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


def _x_start(long_lines: np.ndarray, line: tuple[int, int]) -> int:
    """行簇内长线像素的最左列。"""
    a, b = line
    cols = np.where(long_lines[a:b + 1].any(axis=0))[0]
    return int(cols[0]) if len(cols) else long_lines.shape[1]


def find_systems(gray: np.ndarray) -> list[tuple[int, int]]:
    """返回每个谱表系统的 (y_top, y_bottom)。"""
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 51, 8)
    kernel_w = int(gray.shape[1] * MIN_LINE_WIDTH_RATIO)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_w, 1))
    long_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
    rows = np.where(long_lines.sum(axis=1) > 0)[0]
    if len(rows) == 0:
        return []
    max_x = gray.shape[1] * MAX_X_START_RATIO
    lines = [ln for ln in _cluster(rows, LINE_GAP)
             if _x_start(long_lines, ln) < max_x]
    if not lines:
        return []
    centers = np.array([(a + b) // 2 for a, b in lines])
    systems = []
    for lo_c, hi_c in _cluster(centers, SYSTEM_GAP):
        n = int(((centers >= lo_c) & (centers <= hi_c)).sum())
        if n >= MIN_LINES_PER_SYSTEM:
            # 用实际行坐标而非中心值
            mask = (centers >= lo_c) & (centers <= hi_c)
            y0 = int(min(lines[i][0] for i in range(len(lines)) if mask[i]))
            y1 = int(max(lines[i][1] for i in range(len(lines)) if mask[i]))
            systems.append((y0, y1))
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
