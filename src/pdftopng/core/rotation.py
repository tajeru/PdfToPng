"""ページ回転値の正規化と、画像への適用。

回転値は「時計回りの角度」で 0 / 90 / 180 / 270 のいずれか。
"""
from __future__ import annotations

from PIL import Image

VALID_ROTATIONS: tuple[int, ...] = (0, 90, 180, 270)

# Pillow の ROTATE_* は反時計回りなので、時計回りの角度との対応はこうなる。
_TRANSPOSE = {
    90: Image.Transpose.ROTATE_270,
    180: Image.Transpose.ROTATE_180,
    270: Image.Transpose.ROTATE_90,
}


def normalize(degrees: int) -> int:
    """任意の 90 の倍数を 0〜270 に正規化する（-90 → 270 など）。"""
    degrees = int(degrees)
    if degrees % 90 != 0:
        raise ValueError(f"回転角は 90 の倍数で指定してください（指定値: {degrees}）。")
    return degrees % 360


def rotate(current: int, delta: int) -> int:
    """現在の回転値に delta（時計回り、負なら反時計回り）を加える。"""
    return normalize(current + delta)


def apply(image: Image.Image, rotation: int) -> Image.Image:
    """画像を時計回りに rotation 度回転させる（無劣化の transpose を使う）。"""
    r = normalize(rotation)
    if r == 0:
        return image
    return image.transpose(_TRANSPOSE[r])
