"""ページのサムネイル一覧（モデル + 描画デリゲート + ビュー）。

回転はモデルの rotation に保持するだけで、サムネイル画像自体は回転させない。
描画時に QPainter で回して表示する（元 PDF もサムネイルも書き換えない）。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen
from PySide6.QtWidgets import QAbstractItemView, QListView, QStyle, QStyledItemDelegate

from ..core import rotation as rot
from ..core.document import PageItem
from . import strings, theme

ThumbRole = Qt.UserRole + 1
RotationRole = Qt.UserRole + 2


@dataclass
class PageEntry:
    doc_id: int
    pdf_path: Path
    page_index: int  # 0 始まり
    page_count: int
    rotation: int = 0
    thumb: QImage | None = None


def draw_rotated_image(painter: QPainter, box: QRectF, image: QImage, rotation: int) -> QRectF:
    """image を時計回りに rotation 度回して box 内に収まるよう中央に描く。

    描いた領域（回転後の外接矩形）を返す。
    """
    w, h = image.width(), image.height()
    rw, rh = (h, w) if rotation in (90, 270) else (w, h)
    scale = min(box.width() / max(rw, 1), box.height() / max(rh, 1))
    painter.save()
    painter.setRenderHint(QPainter.SmoothPixmapTransform)
    painter.translate(box.center())
    painter.rotate(rotation)
    target = QRectF(-w * scale / 2, -h * scale / 2, w * scale, h * scale)
    painter.drawImage(target, image)
    painter.restore()
    c = box.center()
    return QRectF(c.x() - rw * scale / 2, c.y() - rh * scale / 2, rw * scale, rh * scale)


# ------------------------------------------------------------------- モデル
class PageModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[PageEntry] = []
        self._rows: dict[tuple[int, int], int] = {}
        self.loaded_thumbs = 0

    # ------------------------------------------------------ Qt インターフェース
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        if role == Qt.DisplayRole:
            return e.pdf_path.stem
        if role == Qt.ToolTipRole:
            text = f"{e.pdf_path.name}\n{e.page_index + 1} / {e.page_count} ページ"
            if e.rotation:
                text += "\n" + strings.PREVIEW_ROTATION.format(deg=e.rotation)
            return text
        if role == ThumbRole:
            return e.thumb
        if role == RotationRole:
            return e.rotation
        return None

    # ------------------------------------------------------ 操作
    def entry(self, row: int) -> PageEntry:
        return self._entries[row]

    def add_document(self, doc_id: int, pdf_path: Path, page_count: int) -> None:
        if page_count <= 0:
            return
        start = len(self._entries)
        self.beginInsertRows(QModelIndex(), start, start + page_count - 1)
        for i in range(page_count):
            self._rows[(doc_id, i)] = start + i
            self._entries.append(PageEntry(doc_id, Path(pdf_path), i, page_count))
        self.endInsertRows()

    def set_thumbnail(self, doc_id: int, page_index: int, image: QImage) -> None:
        row = self._rows.get((doc_id, page_index))
        if row is None:
            return  # クリア済みの PDF からの遅延通知は無視
        e = self._entries[row]
        if e.thumb is None:
            self.loaded_thumbs += 1
        e.thumb = image
        idx = self.index(row)
        self.dataChanged.emit(idx, idx, [ThumbRole])

    def rotate(self, rows: Iterable[int], delta: int) -> None:
        self._update_rotation(rows, lambda current: rot.rotate(current, delta))

    def reset_rotation(self, rows: Iterable[int]) -> None:
        self._update_rotation(rows, lambda current: 0)

    def _update_rotation(self, rows: Iterable[int], fn) -> None:
        rows = [r for r in rows if 0 <= r < len(self._entries)]
        if not rows:
            return
        for r in rows:
            e = self._entries[r]
            e.rotation = fn(e.rotation)
        self.dataChanged.emit(self.index(min(rows)), self.index(max(rows)), [RotationRole])

    def clear(self) -> None:
        self.beginResetModel()
        self._entries.clear()
        self._rows.clear()
        self.loaded_thumbs = 0
        self.endResetModel()

    def rotated_count(self) -> int:
        return sum(1 for e in self._entries if e.rotation)

    def page_items(self) -> list[PageItem]:
        """書き出し用のスナップショット（以後の UI 操作の影響を受けない）。"""
        return [PageItem(e.pdf_path, e.page_index, e.rotation) for e in self._entries]


# --------------------------------------------------------------- デリゲート
class PageDelegate(QStyledItemDelegate):
    CELL = QSize(184, 244)
    _PAD = 6.0
    _LABEL_H = 26.0

    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return self.CELL

    def paint(self, painter: QPainter, option, index) -> None:
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        card = QRectF(option.rect).adjusted(self._PAD, self._PAD, -self._PAD, -self._PAD)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)
        enabled = bool(option.state & QStyle.State_Enabled)

        # カード面
        if selected:
            bg = theme.blend(theme.SURFACE, theme.ACCENT, 0.18)
            border = QPen(QColor(theme.ACCENT), 2)
        elif hovered:
            bg = QColor(theme.HOVER)
            border = QPen(QColor(theme.DASH), 1)
        else:
            bg = QColor(theme.SURFACE)
            border = QPen(QColor(theme.BORDER_SOFT), 1)
        painter.setPen(border)
        painter.setBrush(bg)
        painter.drawRoundedRect(card, 12, 12)

        # サムネイル
        box = QRectF(card.x() + 12, card.y() + 12, card.width() - 24, card.height() - 24 - self._LABEL_H)
        image: QImage | None = index.data(ThumbRole)
        rotation = index.data(RotationRole) or 0
        if image is None or image.isNull():
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(theme.WELL))
            painter.drawRoundedRect(box, 6, 6)
            painter.setPen(QColor(theme.FAINT))
            painter.drawText(box, Qt.AlignCenter, strings.PREVIEW_LOADING)
        else:
            if not enabled:
                painter.setOpacity(0.5)
            drawn = draw_rotated_image(painter, box, image, rotation)
            painter.setOpacity(1.0)
            painter.setPen(QPen(QColor(0, 0, 0, 90), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(drawn)

        # 回転バッジ（右上）
        if rotation:
            self._draw_badge(painter, card, f"↻ {rotation}°")

        # ラベル：左に PDF 名（省略）、右にページ番号
        label_rect = QRectF(card.x() + 12, card.bottom() - self._LABEL_H - 6, card.width() - 24, self._LABEL_H)
        model = index.model()
        entry = model.entry(index.row()) if isinstance(model, PageModel) else None
        page_text = f"p.{entry.page_index + 1}" if entry else ""
        bold = QFont(option.font)
        bold.setBold(True)
        painter.setFont(bold)
        painter.setPen(QColor(theme.TEXT if enabled else theme.FAINT))
        painter.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, page_text)
        page_w = painter.fontMetrics().horizontalAdvance(page_text) + 8
        painter.setFont(option.font)
        painter.setPen(QColor(theme.FAINT))
        name_rect = label_rect.adjusted(0, 0, -page_w, 0)
        name = painter.fontMetrics().elidedText(
            str(index.data(Qt.DisplayRole) or ""), Qt.ElideMiddle, int(name_rect.width())
        )
        painter.drawText(name_rect, Qt.AlignLeft | Qt.AlignVCenter, name)
        painter.restore()

    @staticmethod
    def _draw_badge(painter: QPainter, card: QRectF, text: str) -> None:
        font = QFont(painter.font())
        font.setPointSizeF(8.0)
        font.setBold(True)
        painter.setFont(font)
        w = painter.fontMetrics().horizontalAdvance(text) + 16
        badge = QRectF(card.right() - w - 8, card.y() + 8, w, 20)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(theme.ACCENT3))
        painter.drawRoundedRect(badge, 10, 10)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge, Qt.AlignCenter, text)


# ------------------------------------------------------------------- ビュー
class PageGrid(QListView):
    """サムネイルのグリッド表示。

    キー操作: ← → で選択ページを 90° 回転、R で 180°、↑ ↓ で前後のページへ移動、
    Enter / Space で拡大表示、Ctrl+A で全選択。
    """

    rotateRequested = Signal(int)  # 時計回りの角度（-90 / 90 / 180）
    previewRequested = Signal(int)  # 行

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("cls", "pageGrid")
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setWrapping(True)
        self.setUniformItemSizes(True)
        self.setGridSize(PageDelegate.CELL)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setDragEnabled(False)
        self.setAcceptDrops(False)  # D&D はメインウィンドウで受ける
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalScrollBar().setSingleStep(32)
        self.setMouseTracking(True)
        self.viewport().setAttribute(Qt.WA_Hover, True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setItemDelegate(PageDelegate(self))
        self.doubleClicked.connect(lambda idx: self.previewRequested.emit(idx.row()))

    def selected_rows(self) -> list[int]:
        if self.selectionModel() is None:
            return []
        return sorted(i.row() for i in self.selectionModel().selectedIndexes())

    def select_row(self, row: int) -> None:
        if self.model() is None or not 0 <= row < self.model().rowCount():
            return
        idx = self.model().index(row, 0)
        self.setCurrentIndex(idx)  # ExtendedSelection では単独選択になる
        self.scrollTo(idx)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if event.modifiers() in (Qt.NoModifier, Qt.KeypadModifier):
            if key == Qt.Key_Left:
                self.rotateRequested.emit(-90)
                return
            if key == Qt.Key_Right:
                self.rotateRequested.emit(90)
                return
            if key == Qt.Key_R:
                self.rotateRequested.emit(180)
                return
            if key in (Qt.Key_Up, Qt.Key_Down):
                current = self.currentIndex().row() if self.currentIndex().isValid() else -1
                step = -1 if key == Qt.Key_Up else 1
                self.select_row(max(0, current + step) if current >= 0 else 0)
                return
            if key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
                if self.currentIndex().isValid():
                    self.previewRequested.emit(self.currentIndex().row())
                return
        super().keyPressEvent(event)
