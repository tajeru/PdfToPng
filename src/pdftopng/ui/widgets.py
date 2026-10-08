"""カスタムウィジェット群（テーマ対応の再利用部品）。

- PdfDropArea      : クリック / D&D で PDF を受け取るヒーロー領域
- SegmentedControl : ラジオボタン代替のセグメント切替
- ElidedLabel      : 幅に応じて省略表示するラベル
- SpinBox          : テーマ色の矢印を描くスピンボックス
- logo_pixmap / rotate_icon : QPainter 描画のアイコン

ElidedLabel・SegmentedControl・SpinBox・ドロップ領域の描画は
ImageToPdf の ui/widgets.py と同じ実装。
"""
from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve,
    QPointF,
    QRectF,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDropEvent,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from . import strings, theme


def dropped_local_paths(event) -> list[str]:
    """D&D イベントからローカルパスの一覧を取り出す。"""
    md = event.mimeData()
    if not md.hasUrls():
        return []
    return [url.toLocalFile() for url in md.urls() if url.isLocalFile()]


# ---------------------------------------------------------------- ElidedLabel
class ElidedLabel(QLabel):
    """幅が足りないときに省略記号（…）で切り詰めるラベル。

    setText ではなく setFullText を使う。レイアウトを押し広げないよう
    最小幅を 0 として扱う。
    """

    def __init__(self, text: str = "", parent=None, mode: Qt.TextElideMode = Qt.ElideMiddle) -> None:
        super().__init__(parent)
        self._full = text or ""
        self._mode = mode
        self._refresh()

    def setFullText(self, text: str) -> None:  # noqa: N802
        self._full = text or ""
        self._refresh()

    def fullText(self) -> str:  # noqa: N802
        return self._full

    def minimumSizeHint(self):  # noqa: N802
        hint = super().minimumSizeHint()
        hint.setWidth(0)
        return hint

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh()

    def _refresh(self) -> None:
        width = max(24, self.width() - 2)
        self.setText(self.fontMetrics().elidedText(self._full, self._mode, width))


# ----------------------------------------------------------- SegmentedControl
class SegmentedControl(QFrame):
    """排他選択のセグメント切替（QRadioButton の代替）。"""

    dataChanged = Signal(object)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("cls", "segmented")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(3, 3, 3, 3)
        lay.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.idToggled.connect(self._on_toggled)
        self._data: list[object] = []

    def addSegment(self, text: str, data: object) -> QPushButton:  # noqa: N802
        btn = QPushButton(text)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setProperty("cls", "segment")
        index = len(self._data)
        self._data.append(data)
        self._group.addButton(btn, index)
        self.layout().addWidget(btn)
        if index == 0:
            btn.setChecked(True)
        return btn

    def currentData(self) -> object:  # noqa: N802
        index = self._group.checkedId()
        return self._data[index] if index >= 0 else None

    def setCurrentData(self, data: object) -> None:  # noqa: N802
        for index, d in enumerate(self._data):
            if d == data:
                self._group.button(index).setChecked(True)
                return

    def _on_toggled(self, index: int, checked: bool) -> None:
        if checked:
            self.dataChanged.emit(self._data[index])


# ------------------------------------------------- 矢印付き入力（QSS 対応）
def _draw_chevron(painter: QPainter, cx: float, cy: float, *, up: bool, enabled: bool) -> None:
    """幅約 9px の山形矢印を (cx, cy) 中心に描く。"""
    color = QColor(theme.SUB if enabled else theme.FAINT)
    pen = QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    painter.setPen(pen)
    dy = -2.2 if up else 2.2
    painter.drawPolyline(QPolygonF([
        QPointF(cx - 4.2, cy - dy),
        QPointF(cx, cy + dy),
        QPointF(cx + 4.2, cy - dy),
    ]))


class SpinBox(QSpinBox):
    """上下ボタンの矢印を自前描画するスピンボックス。

    QSS で ::up-button 等を装飾すると標準矢印が描かれなくなるため描き足す。
    """

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        cx = self.width() - 11.0
        _draw_chevron(painter, cx, self.height() * 0.32, up=True, enabled=self.isEnabled())
        _draw_chevron(painter, cx, self.height() * 0.68, up=False, enabled=self.isEnabled())


# ------------------------------------------------------------- アイコン描画
def _accent_gradient(rect: QRectF) -> QLinearGradient:
    grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
    grad.setColorAt(0.0, QColor(theme.ACCENT))
    grad.setColorAt(0.6, QColor(theme.ACCENT2))
    grad.setColorAt(1.0, QColor(theme.ACCENT3))
    return grad


def _make_canvas(size: int, dpr: float) -> tuple[QPixmap, QPainter]:
    pm = QPixmap(round(size * dpr), round(size * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    return pm, painter


def _page_glyph(rect: QRectF) -> QPainterPath:
    """右上が折れた紙のシルエットパス。"""
    x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
    fold = w * 0.30
    path = QPainterPath()
    path.moveTo(x, y)
    path.lineTo(x + w - fold, y)
    path.lineTo(x + w, y + fold)
    path.lineTo(x + w, y + h)
    path.lineTo(x, y + h)
    path.closeSubpath()
    return path


def _draw_rotate_arrow(p: QPainter, cx: float, cy: float, r: float, color: QColor,
                       width: float, *, clockwise: bool) -> None:
    """(cx, cy) 中心・半径 r の 270° の円弧矢印を描く。"""
    start = 120.0 if clockwise else 60.0
    sweep = -270.0 if clockwise else 270.0
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    arc = QPainterPath()
    arc.arcMoveTo(rect, start)
    arc.arcTo(rect, start, sweep)
    p.drawPath(arc)

    # 矢じり：終点での進行方向（画面座標）に三角形を置く。
    end = math.radians(start + sweep)
    ex, ey = cx + r * math.cos(end), cy - r * math.sin(end)
    sign = 1.0 if clockwise else -1.0
    dx, dy = sign * math.sin(end), sign * math.cos(end)
    nx, ny = -dy, dx
    a = r * 0.75
    tip = QPointF(ex + dx * a * 0.65, ey + dy * a * 0.65)
    b1 = QPointF(ex - dx * a * 0.35 + nx * a * 0.6, ey - dy * a * 0.35 + ny * a * 0.6)
    b2 = QPointF(ex - dx * a * 0.35 - nx * a * 0.6, ey - dy * a * 0.35 - ny * a * 0.6)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPolygon(QPolygonF([tip, b1, b2]))


def logo_pixmap(size: int, dpr: float = 1.0) -> QPixmap:
    """角丸グラデーションタイル + 白抜きの紙 + 回転矢印のロゴマーク。"""
    pm, p = _make_canvas(size, dpr)
    rect = QRectF(0, 0, size, size)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_accent_gradient(rect)))
    p.drawRoundedRect(rect, size * 0.28, size * 0.28)

    white = QColor("#FFFFFF")
    white.setAlpha(242)
    p.setBrush(white)
    page = QRectF(size * 0.27, size * 0.20, size * 0.38, size * 0.50)
    p.drawPath(_page_glyph(page))

    # 右下に回転矢印（タイル色の縁取りの上に白）。
    cx, cy, r = size * 0.66, size * 0.67, size * 0.15
    ring = QColor(theme.ACCENT2)
    p.setBrush(ring)
    p.drawEllipse(QPointF(cx, cy), r * 1.75, r * 1.75)
    _draw_rotate_arrow(p, cx, cy, r, white, max(1.5, size * 0.05), clockwise=True)
    p.end()
    return pm


def pdf_pixmap(size: int, dpr: float = 1.0, *, opacity: float = 1.0) -> QPixmap:
    """ドロップ領域用の PDF アイコン（グラデーションの紙 + 下向き矢印バッジ）。"""
    pm, p = _make_canvas(size, dpr)
    p.setOpacity(opacity)
    area = QRectF(size * 0.16, size * 0.06, size * 0.62, size * 0.82)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(_accent_gradient(area)))
    p.drawPath(_page_glyph(area))

    # 本文の行を模した淡い線。
    line = QColor("#FFFFFF")
    line.setAlpha(70)
    p.setBrush(line)
    for i in range(3):
        y = area.y() + area.height() * (0.42 + i * 0.14)
        w = area.width() * (0.62 if i < 2 else 0.40)
        p.drawRoundedRect(QRectF(area.x() + area.width() * 0.16, y, w, size * 0.045), 2, 2)

    # 右下バッジ（↓）。
    d = size * 0.36
    bx = size * 0.94 - d
    by = size * 0.96 - d
    p.setBrush(QColor(theme.SURFACE))
    p.drawEllipse(QRectF(bx - size * 0.045, by - size * 0.045, d + size * 0.09, d + size * 0.09))
    p.setBrush(QColor(theme.HOVER))
    p.drawEllipse(QRectF(bx, by, d, d))
    pen = QPen(QColor(theme.SUB), max(2.0, size * 0.045), Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    cx, cy = bx + d / 2, by + d / 2
    p.drawLine(QPointF(cx, cy - d * 0.20), QPointF(cx, cy + d * 0.14))
    p.drawPolyline(QPolygonF([
        QPointF(cx - d * 0.14, cy + d * 0.01),
        QPointF(cx, cy + d * 0.16),
        QPointF(cx + d * 0.14, cy + d * 0.01),
    ]))
    p.end()
    return pm


def rotate_icon(size: int = 16, dpr: float = 1.0, *, clockwise: bool) -> QIcon:
    """回転ボタン用アイコン（通常色と無効色の 2 状態）。"""
    icon = QIcon()
    for mode, color in ((QIcon.Normal, theme.TEXT), (QIcon.Disabled, theme.FAINT)):
        pm, p = _make_canvas(size, dpr)
        _draw_rotate_arrow(
            p, size / 2, size / 2 + size * 0.04, size * 0.30,
            QColor(color), max(1.4, size * 0.10), clockwise=clockwise,
        )
        p.end()
        icon.addPixmap(pm, mode)
    return icon


# ----------------------------------------------------------------- PdfDropArea
class PdfDropArea(QFrame):
    """PDF を受け取るヒーロー領域（ページ未読み込み時に表示）。

    - PDF / フォルダの D&D で filesDropped(list[str]) を emit
    - クリック / Space / Enter で clicked を emit（選択ダイアログ起動用）
    - ドラッグ中は破線ボーダーがグラデーションに変わるグローアニメーション
    """

    filesDropped = Signal(list)
    clicked = Signal()

    _RADIUS = 16.0
    _MARGIN = 5.0  # グロー描画分の余白

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumHeight(220)
        self._pressed = False

        self._glow = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._on_glow)

        self._icon = QLabel()
        self._icon.setAlignment(Qt.AlignCenter)
        title = QLabel(strings.DROP_TITLE)
        title.setProperty("cls", "dropTitle")
        title.setAlignment(Qt.AlignCenter)
        sub = QLabel(strings.DROP_SUB)
        sub.setProperty("cls", "dropSub")
        sub.setAlignment(Qt.AlignCenter)
        meta = QLabel(strings.DROP_FORMATS)
        meta.setProperty("cls", "dropMeta")
        meta.setAlignment(Qt.AlignCenter)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 20, 28, 16)
        lay.setSpacing(4)
        lay.addStretch(1)
        lay.addWidget(self._icon)
        lay.addSpacing(8)
        lay.addWidget(title)
        lay.addWidget(sub)
        lay.addStretch(1)
        lay.addWidget(meta)
        self._update_icon()

    def _update_icon(self) -> None:
        self._icon.setPixmap(
            pdf_pixmap(64, self.devicePixelRatioF(), opacity=1.0 if self.isEnabled() else 0.38)
        )

    # ------------------------------------------------------------ D&D
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802
        if self.isEnabled() and dropped_local_paths(event):
            event.acceptProposedAction()
            self._animate_glow(1.0)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._animate_glow(0.0)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        paths = dropped_local_paths(event)
        self._animate_glow(0.0)
        if paths:
            event.acceptProposedAction()
            self.filesDropped.emit(paths)
        else:
            event.ignore()

    # ------------------------------------------------------------ クリック
    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self.isEnabled():
            self._pressed = True
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if (
            self._pressed
            and event.button() == Qt.LeftButton
            and self.isEnabled()
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        self._pressed = False
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if self.isEnabled() and event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------ 再描画契機
    def enterEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().leaveEvent(event)

    def focusInEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.update()
        super().focusOutEvent(event)

    def changeEvent(self, event) -> None:  # noqa: N802
        if event.type() == event.Type.EnabledChange:
            self._update_icon()
            self.update()
        super().changeEvent(event)

    # ------------------------------------------------------------ グロー
    def _animate_glow(self, target: float) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._glow)
        self._anim.setEndValue(target)
        self._anim.start()

    def _on_glow(self, value) -> None:
        self._glow = float(value)
        self.update()

    # ------------------------------------------------------------ 描画
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        m = self._MARGIN
        rect = QRectF(self.rect()).adjusted(m, m, -m, -m)
        t = self._glow
        enabled = self.isEnabled()
        hovered = enabled and self.underMouse()

        # 背景（ドラッグ中はアクセント方向へわずかに色づく）。
        if not enabled:
            bg = QColor(theme.WELL)
        elif t > 0:
            bg = theme.blend(theme.SURFACE, theme.ACCENT, 0.07 * t)
        elif hovered:
            bg = theme.blend(theme.SURFACE, "#FFFFFF", 0.025)
        else:
            bg = QColor(theme.SURFACE)
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        # 外周グロー（ドラッグ中のみ）。
        if t > 0:
            halo = QColor(theme.ACCENT2)
            halo.setAlphaF(0.22 * t)
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(halo, 7))
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)

        # 破線ボーダー。通常色とグラデーションを t でクロスフェードする。
        dash = [4.0, 3.2]
        painter.setBrush(Qt.NoBrush)
        if t < 1.0:
            if not enabled:
                color = QColor(theme.BORDER_SOFT)
            elif hovered or self.hasFocus():
                color = QColor(theme.DASH)
            else:
                color = QColor("#2F3A4C")
            color.setAlphaF(color.alphaF() * (1.0 - t))
            pen = QPen(color, 1.6)
            pen.setCapStyle(Qt.RoundCap)
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern(dash)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)
        if t > 0:
            grad = QLinearGradient(rect.topLeft(), rect.topRight())
            for pos, name in ((0.0, theme.ACCENT), (0.5, theme.ACCENT2), (1.0, theme.ACCENT3)):
                color = QColor(name)
                color.setAlphaF(t)
                grad.setColorAt(pos, color)
            pen = QPen(QBrush(grad), 1.8 + 0.6 * t)
            pen.setCapStyle(Qt.RoundCap)
            pen.setStyle(Qt.CustomDashLine)
            pen.setDashPattern(dash)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, self._RADIUS, self._RADIUS)
