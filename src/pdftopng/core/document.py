"""PDF の読み込みとページのレンダリング（pypdfium2）。

PDFium はスレッドセーフではなく、別ドキュメントであっても複数スレッドから
同時に呼び出してはいけない。そのため PDFium を触る処理はすべて
PDFIUM_LOCK を取得してから行う（サムネイル生成・プレビュー・書き出しが
別スレッドで並行しても安全にするため）。
"""
from __future__ import annotations

import re
import threading
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

PDFIUM_LOCK = threading.RLock()

PDF_EXT = ".pdf"


class PdfOpenError(Exception):
    """PDF を開けなかった（破損・パスワード付き・読み取り不可など）。"""


@dataclass(frozen=True)
class PageItem:
    """書き出し対象の 1 ページ。rotation は時計回りの角度（0/90/180/270）。"""

    pdf_path: Path
    page_index: int  # 0 始まり
    rotation: int = 0


def is_pdf(path: str | Path) -> bool:
    return Path(path).suffix.lower() == PDF_EXT


def natural_key(text: str) -> list:
    """数字部分を数値として比較するソートキー（1, 2, 10 の順になる）。"""
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def collect_pdfs(paths: Iterable[str | Path]) -> list[Path]:
    """D&D などで渡されたパス群から PDF を集める。

    - PDF ファイルはそのまま（渡された順）
    - フォルダは直下の PDF を自然順で展開する（サブフォルダは見ない）
    - それ以外は無視する
    """
    result: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            children = [c for c in p.iterdir() if c.is_file() and is_pdf(c)]
            result.extend(sorted(children, key=lambda c: natural_key(c.name)))
        elif p.is_file() and is_pdf(p):
            result.append(p)
    return result


class PdfFile:
    """1 つの PDF を開いてページをレンダリングする。with 文で使う。

    日本語パスでも確実に開けるよう、ファイルは Python 側で開いて
    ファイルオブジェクトを PDFium に渡す。
    """

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._doc = None
        try:
            self._fh = self.path.open("rb")
        except OSError as e:
            raise PdfOpenError(f"ファイルを開けません（{e.strerror or e}）。") from e
        try:
            with PDFIUM_LOCK:
                self._doc = pdfium.PdfDocument(self._fh)
                self.page_count: int = len(self._doc)
        except pdfium.PdfiumError as e:
            self._fh.close()
            if "password" in str(e).lower():
                raise PdfOpenError("パスワードで保護された PDF には対応していません。") from e
            raise PdfOpenError("PDF を読み込めません（破損しているか、PDF ではありません）。") from e
        except Exception:
            self._fh.close()
            raise

    # ------------------------------------------------------------ レンダリング
    def render(self, index: int, scale: float) -> Image.Image:
        """ページを scale 倍（1.0 = 72dpi）でレンダリングして RGB 画像を返す。

        PDF 側の /Rotate 指定は反映済みの向きで返る（これを回転 0° とみなす）。
        """
        if not 0 <= index < self.page_count:
            raise IndexError(f"ページ番号が範囲外です: {index + 1} / {self.page_count}")
        with PDFIUM_LOCK:
            page = self._doc[index]
            try:
                image = page.render(scale=scale).to_pil()
            finally:
                page.close()
        return image if image.mode == "RGB" else image.convert("RGB")

    def render_dpi(self, index: int, dpi: int) -> Image.Image:
        return self.render(index, dpi / 72.0)

    def render_fit(self, index: int, max_px: int) -> Image.Image:
        """長辺が max_px になるようにレンダリングする（サムネイル・プレビュー用）。"""
        with PDFIUM_LOCK:
            page = self._doc[index]
            try:
                width, height = page.get_size()
            finally:
                page.close()
        return self.render(index, max_px / max(width, height, 1.0))

    # ------------------------------------------------------------ 後始末
    def close(self) -> None:
        if self._doc is not None:
            with PDFIUM_LOCK:
                self._doc.close()
            self._doc = None
        if not self._fh.closed:
            self._fh.close()

    def __enter__(self) -> "PdfFile":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
