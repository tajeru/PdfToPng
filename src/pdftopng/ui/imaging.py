"""Pillow 画像と Qt 画像の変換。"""
from __future__ import annotations

from PIL import Image
from PySide6.QtGui import QImage


def pil_to_qimage(image: Image.Image) -> QImage:
    """PIL 画像を QImage に変換する（別スレッドからも呼べる）。

    QImage はバッファを参照するだけなので copy() でデータを所有させる。
    """
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    data = rgb.tobytes("raw", "RGB")
    qimage = QImage(data, rgb.width, rgb.height, rgb.width * 3, QImage.Format_RGB888)
    return qimage.copy()
