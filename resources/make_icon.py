"""アプリのロゴマークから resources/app.ico を生成する。

使い方:  python resources/make_icon.py
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    from PIL import Image
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtWidgets import QApplication

    from pdftopng.ui.widgets import logo_pixmap

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 - QPixmap に必要
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    logo_pixmap(256).save(buf, "PNG")
    image = Image.open(io.BytesIO(bytes(buf.data())))

    out = ROOT / "resources" / "app.ico"
    image.save(out, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"生成しました: {out}")


if __name__ == "__main__":
    main()
