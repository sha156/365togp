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
