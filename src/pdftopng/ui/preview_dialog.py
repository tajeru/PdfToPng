"""1 ページを大きく表示して向きを確認・変更するダイアログ。

回転はメイン画面と同じ PageModel を直接更新するので、一覧にも即時反映される。
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..config import PREVIEW_PX
from ..core.document import PdfFile
from ..logging_setup import get_logger
from . import strings, theme
from .imaging import pil_to_qimage
from .page_grid import PageModel, draw_rotated_image
from .widgets import ElidedLabel, rotate_icon

log = get_logger(__name__)


class _Canvas(QWidget):
    """画像を回転・縮小して中央に描くだけの領域。"""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._image: QImage | None = None
        self._rotation = 0
        self._message = ""
        self.setMinimumSize(320, 320)

    def set_image(self, image: QImage | None, rotation: int, message: str = "") -> None:
        self._image = image
        self._rotation = rotation
        self._message = message
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        area = QRectF(self.rect())
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.WELL))
        p.drawRoundedRect(area, 16, 16)
        if self._image is None or self._image.isNull():
            p.setPen(QColor(theme.FAINT))
            p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, self._message)
            return
        draw_rotated_image(p, area.adjusted(20, 20, -20, -20), self._image, self._rotation)


class PreviewDialog(QDialog):
    def __init__(self, model: PageModel, row: int, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dialog")
        self.setWindowTitle(strings.PREVIEW_TITLE)
        self.resize(920, 1000)
        self._model = model
        self._row = row
        self._image: QImage | None = None
        self._error = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        head = QHBoxLayout()
        self.lbl_title = ElidedLabel()
        self.lbl_title.setProperty("cls", "h2")
        self.lbl_rotation = QLabel()
        self.lbl_rotation.setProperty("cls", "chip")
        head.addWidget(self.lbl_title, 1)
        head.addWidget(self.lbl_rotation, 0, Qt.AlignVCenter)
        root.addLayout(head)

        self.canvas = _Canvas()
        root.addWidget(self.canvas, 1)

        keys = QLabel(strings.PREVIEW_KEYS)
        keys.setProperty("cls", "hint")
        keys.setAlignment(Qt.AlignCenter)
        root.addWidget(keys)

        bar = QHBoxLayout()
        bar.setSpacing(8)
        self.btn_prev = self._button(strings.PREVIEW_PREV, lambda: self._go(-1))
        self.btn_next = self._button(strings.PREVIEW_NEXT, lambda: self._go(1))
        bar.addWidget(self.btn_prev)
        bar.addWidget(self.btn_next)
        bar.addStretch(1)
        dpr = self.devicePixelRatioF()
        left = self._button(strings.BTN_ROT_LEFT, lambda: self._rotate(-90))
        left.setIcon(rotate_icon(16, dpr, clockwise=False))
        right = self._button(strings.BTN_ROT_RIGHT, lambda: self._rotate(90))
        right.setIcon(rotate_icon(16, dpr, clockwise=True))
        bar.addWidget(left)
        bar.addWidget(right)
        bar.addWidget(self._button(strings.BTN_ROT_180, lambda: self._rotate(180)))
        bar.addWidget(self._button(strings.BTN_ROT_RESET, self._reset))
        bar.addSpacing(12)
        close = QPushButton(strings.PREVIEW_CLOSE)
        close.setProperty("cls", "ghost")
        close.setCursor(Qt.PointingHandCursor)
        close.clicked.connect(self.accept)
        bar.addWidget(close)
        root.addLayout(bar)

        theme.enable_dark_title_bar(self)
        self._load()

    def _button(self, text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("cls", "ghostSmall")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFocusPolicy(Qt.NoFocus)  # キー操作をダイアログで受けるため
        btn.clicked.connect(slot)
        return btn

    def current_row(self) -> int:
        return self._row

    # ------------------------------------------------------------ 表示
    def _load(self) -> None:
        entry = self._model.entry(self._row)
        self._image = None
        self._error = ""
        # まずサムネイルで即表示し、高解像度のレンダリング後に差し替える。
        self.canvas.set_image(entry.thumb, entry.rotation, strings.PREVIEW_LOADING)
        self._refresh_labels()
        if self.isVisible():
            self.canvas.repaint()  # レンダリング（同期処理）の前に描画させる
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            with PdfFile(entry.pdf_path) as pdf:
                self._image = pil_to_qimage(pdf.render_fit(entry.page_index, PREVIEW_PX))
        except Exception as e:  # noqa: BLE001
            log.exception("プレビューの生成に失敗: %s p.%d", entry.pdf_path, entry.page_index + 1)
            self._error = strings.PREVIEW_ERROR.format(message=e)
        finally:
            QApplication.restoreOverrideCursor()
        self._refresh()

    def _refresh(self) -> None:
        entry = self._model.entry(self._row)
        image = self._image if self._image is not None else (None if self._error else entry.thumb)
        self.canvas.set_image(image, entry.rotation, self._error or strings.PREVIEW_LOADING)
        self._refresh_labels()

    def _refresh_labels(self) -> None:
        entry = self._model.entry(self._row)
        self.lbl_title.setFullText(
            strings.PREVIEW_PAGE.format(
                name=entry.pdf_path.name, page=entry.page_index + 1, count=entry.page_count
            )
        )
        self.lbl_rotation.setText(strings.PREVIEW_ROTATION.format(deg=entry.rotation))
        self.btn_prev.setEnabled(self._row > 0)
        self.btn_next.setEnabled(self._row < self._model.rowCount() - 1)

    # ------------------------------------------------------------ 操作
    def _rotate(self, delta: int) -> None:
        self._model.rotate([self._row], delta)
        self._refresh()

    def _reset(self) -> None:
        self._model.reset_rotation([self._row])
        self._refresh()

    def _go(self, step: int) -> None:
        row = self._row + step
        if 0 <= row < self._model.rowCount():
            self._row = row
            self._load()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key_Left:
            self._rotate(-90)
        elif key == Qt.Key_Right:
            self._rotate(90)
        elif key == Qt.Key_R:
            self._rotate(180)
        elif key in (Qt.Key_Up, Qt.Key_PageUp):
            self._go(-1)
        elif key in (Qt.Key_Down, Qt.Key_PageDown):
            self._go(1)
        else:
            super().keyPressEvent(event)
