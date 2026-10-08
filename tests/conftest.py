"""テスト共通設定。src レイアウトを import 可能にし、テスト用 PDF の生成ヘルパーを提供。"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

MARK = 30  # 左上に置く目印（赤い正方形）の一辺


def page_image(size: tuple[int, int] = (100, 150)) -> Image.Image:
    """白地の左上に赤い目印を置いた画像（向きの判定に使う）。"""
    img = Image.new("RGB", size, (255, 255, 255))
    img.paste((220, 30, 30), (0, 0, MARK, MARK))
    return img


def _make_pdf(path: Path, sizes: list[tuple[int, int]] | None = None) -> Path:
    """sizes の各サイズ（px = pt）のページを持つ PDF を作る。"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    images = [page_image(s) for s in (sizes or [(100, 150)])]
    images[0].save(path, "PDF", save_all=True, append_images=images[1:], resolution=72.0)
    return path


@pytest.fixture
def make_pdf():
    return _make_pdf


def is_red(pixel) -> bool:
    r, g, b = pixel[:3]
    return r > 170 and g < 110 and b < 110
