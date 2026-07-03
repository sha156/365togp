import pytest

from render import render_page
from segment import segment_page

PDF = "365日！！电吉他手的养成计划.pdf"


@pytest.fixture(scope="module")
def pages(tmp_path_factory):
    d = tmp_path_factory.mktemp("pages")
    return [render_page(PDF, i, str(d)) for i in (20, 21)]


def test_page20_has_4_systems(pages, tmp_path):
    saved = segment_page(str(pages[0]), str(tmp_path / "w"))
    assert len(saved) == 4  # 每日必弹 + 周一/二/三
    assert saved[0].name == "system_01.png"
    assert (tmp_path / "w" / "system_01@2x.png").exists()


def test_page21_has_3_systems(pages, tmp_path):
    saved = segment_page(str(pages[1]), str(tmp_path / "w"), start_index=5)
    assert len(saved) == 3  # 周四/五/六（周日无谱）
    assert saved[0].name == "system_05.png"
