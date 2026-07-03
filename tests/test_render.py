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
