"""重い処理を別スレッドで走らせる QThread ワーカー。

- ThumbnailWorker: PDF を開いてページ数を通知し、サムネイルを順次生成する
- ExportWorker   : core/exporter で PNG を書き出す
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal

from .config import THUMB_PX, ExportOptions
from .core.document import PageItem, PdfFile, PdfOpenError
from .core.exporter import ExportResult, export
from .logging_setup import get_logger
from .ui.imaging import pil_to_qimage

log = get_logger(__name__)


class ThumbnailWorker(QThread):
    """jobs = [(doc_id, pdf_path), ...] を処理する。

    まず全 PDF を開いてページ数を通知し（一覧の枠をすぐ出すため）、
    その後サムネイルを 1 枚ずつ生成して通知する。
    """

    opened = Signal(int, int)  # doc_id, page_count
    openFailed = Signal(int, str)  # doc_id, message
    thumbnail = Signal(int, int, object)  # doc_id, page_index, QImage

    def __init__(self, jobs: list[tuple[int, Path]], parent=None) -> None:
        super().__init__(parent)
        self._jobs = list(jobs)
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401
        ok: list[tuple[int, Path, int]] = []
        for doc_id, path in self._jobs:
            if self._cancel:
                return
            try:
                with PdfFile(path) as pdf:
                    count = pdf.page_count
            except PdfOpenError as e:
                self.openFailed.emit(doc_id, str(e))
                continue
            except Exception as e:  # noqa: BLE001
                log.exception("PDF を開けません: %s", path)
                self.openFailed.emit(doc_id, str(e))
                continue
            self.opened.emit(doc_id, count)
            ok.append((doc_id, path, count))

        for doc_id, path, count in ok:
            if self._cancel:
                return
            try:
                with PdfFile(path) as pdf:
                    for index in range(count):
                        if self._cancel:
                            return
                        try:
                            image = pdf.render_fit(index, THUMB_PX)
                        except Exception:  # noqa: BLE001 - 1 枚の失敗で止めない
                            log.exception("サムネイル生成に失敗: %s p.%d", path, index + 1)
                            continue
                        self.thumbnail.emit(doc_id, index, pil_to_qimage(image))
            except Exception:  # noqa: BLE001
                log.exception("サムネイル生成中に PDF を開けません: %s", path)


class ExportWorker(QThread):
    progress = Signal(int, int, str)  # done, total, current_name
    status = Signal(str)
    completed = Signal(object)  # ExportResult
    failed = Signal(str)

    def __init__(self, pages: list[PageItem], options: ExportOptions, parent=None) -> None:
        super().__init__(parent)
        self._pages = list(pages)
        self._options = options
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401
        try:
            result: ExportResult = export(
                self._pages,
                self._options,
                on_progress=lambda done, total, name: self.progress.emit(done, total, name),
                on_status=self.status.emit,
                should_cancel=lambda: self._cancel,
            )
            self.completed.emit(result)
        except Exception as e:  # noqa: BLE001 - 想定外は致命扱いで通知
            log.exception("書き出し中に致命的エラー")
            self.failed.emit(str(e))
