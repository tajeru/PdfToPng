import pytest
from conftest import MARK, is_red, page_image

from pdftopng.core import rotation


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, 0), (90, 90), (360, 0), (450, 90), (-90, 270), (-180, 180)],
)
def test_normalize(value, expected):
    assert rotation.normalize(value) == expected


def test_normalize_rejects_non_right_angles():
    with pytest.raises(ValueError):
        rotation.normalize(45)


def test_rotate_accumulates():
    assert rotation.rotate(0, -90) == 270
    assert rotation.rotate(270, 90) == 0
    assert rotation.rotate(90, 180) == 270


def test_apply_zero_returns_same_image():
    img = page_image()
    assert rotation.apply(img, 0) is img


@pytest.mark.parametrize(
    ("deg", "corner"),
    [(90, "top_right"), (180, "bottom_right"), (270, "bottom_left")],
)
def test_apply_is_clockwise(deg, corner):
    out = rotation.apply(page_image((100, 150)), deg)
    assert out.size == ((150, 100) if deg in (90, 270) else (100, 150))
    w, h = out.size
    c = MARK // 2
    points = {
        "top_right": (w - c, c),
        "bottom_right": (w - c, h - c),
        "bottom_left": (c, h - c),
    }
    assert is_red(out.getpixel(points[corner]))
    assert not is_red(out.getpixel((c, c)))
