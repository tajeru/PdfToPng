"""メインウィンドウ。

画面は「ヘッダー → ツールバー → ページ一覧（未読み込み時はドロップ領域）
→ 書き出し設定カード → 進捗 → アクション」の縦積み。
文言は ui/strings.py、配色は ui/theme.py。処理は worker 経由で core を呼ぶだけ。
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import APP_NAME, __version__
from ..config import (
    DEFAULT_DPI,
    MAX_DPI,
    MIN_DPI,
    ExportOptions,
    Settings,
    load_settings,
    save_settings,
)
from ..core.document import collect_pdfs
from ..core.exporter import ExportResult
from ..worker import ExportWorker, ThumbnailWorker
from . import strings, theme
from .page_grid import PageGrid, PageModel
from .preview_dialog import PreviewDialog
from .widgets import (
    ElidedLabel,
    PdfDropArea,
    SegmentedControl,
    SpinBox,
    dropped_local_paths,
    logo_pixmap,
    rotate_icon,
)


def _path_key(path: Path) -> str:
    """同一ファイル判定用のキー（大文字小文字・相対パスの違いを吸収）。"""
    return os.path.normcase(str(Path(path).resolve()))


class MainWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("window")
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.setMinimumSize(860, 640)
        self.setAcceptDrops(True)

        self.model = PageModel(self)
        self._docs: dict[int, Path] = {}  # 読み込み中/済みの PDF（doc_id → パス）
        self._unopened: set[int] = set()  # ページ数がまだ分からない doc_id
        self._next_doc_id = 1
        self._pending: list[tuple[int, Path]] = []
        self._load_errors: list[str] = []
        self._thumb_worker: ThumbnailWorker | None = None
        self._export_worker: ExportWorker | None = None
        self._output_dir: Path | None = None
        self._last_output: Path | None = None
        self._last_open_dir: str = ""

        self._build_ui()
        self._restore_settings()
        theme.enable_dark_title_bar(self)
        self.resize(1120, 820)
        self._refresh_state()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 22, 28, 22)
        root.setSpacing(14)

        root.addLayout(self._build_header())
        root.addLayout(self._build_toolbar())

        self.drop = PdfDropArea()
        self.drop.filesDropped.connect(self._add_paths)
        self.drop.clicked.connect(self._pick_pdfs)
        self.grid = PageGrid()
        self.grid.setModel(self.model)
        self.grid.rotateRequested.connect(self._rotate_selected)
        self.grid.previewRequested.connect(self._open_preview)
        self.grid.customContextMenuRequested.connect(self._show_context_menu)
        self.grid.selectionModel().selectionChanged.connect(self._refresh_state)
        self.model.dataChanged.connect(self._refresh_state)
        self.model.rowsInserted.connect(self._refresh_state)
        self.model.modelReset.connect(self._refresh_state)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.drop)
        self.stack.addWidget(self.grid)
        root.addWidget(self.stack, 1)

        root.addWidget(self._build_options_card())
        root.addLayout(self._build_progress_section())
        root.addLayout(self._build_actions())

        # 書き出し中に無効化する入力群（キャンセル以外）。
        self._lockable: tuple[QWidget, ...] = (
            self.btn_add,
            self.btn_clear,
            self.drop,
            self.grid,
            self.spin_dpi,
            self.seg_out,
            self.btn_out,
            self.btn_start,
        )
        self._update_output_controls()

    def _build_header(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(14)
        logo = QLabel()
        logo.setPixmap(logo_pixmap(44, self.devicePixelRatioF()))
        lay.addWidget(logo, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(2)
        name_row = QHBoxLayout()
        name_row.setSpacing(10)
        title = QLabel(APP_NAME)
        title.setProperty("cls", "h1")
        chip = QLabel(f"v{__version__}")
        chip.setProperty("cls", "chip")
        name_row.addWidget(title)
        name_row.addWidget(chip, 0, Qt.AlignVCenter)
        name_row.addStretch(1)
        col.addLayout(name_row)
        tagline = QLabel(strings.TAGLINE)
        tagline.setProperty("cls", "tagline")
        col.addWidget(tagline)
        lay.addLayout(col, 1)
        return lay

    def _build_toolbar(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(8)
        dpr = self.devicePixelRatioF()

        self.btn_add = self._small_button(strings.BTN_ADD, self._pick_pdfs)
        self.btn_clear = self._small_button(strings.BTN_CLEAR, self._clear)
        lay.addWidget(self.btn_add)
        lay.addWidget(self.btn_clear)

        sep = QFrame()
        sep.setProperty("cls", "vsep")
        sep.setFixedSize(1, 22)
        lay.addSpacing(6)
        lay.addWidget(sep)
        lay.addSpacing(6)

        self.btn_rot_left = self._small_button(strings.BTN_ROT_LEFT, lambda: self._rotate_selected(-90))
        self.btn_rot_left.setIcon(rotate_icon(16, dpr, clockwise=False))
        self.btn_rot_left.setToolTip(strings.TIP_ROT_LEFT)
        self.btn_rot_right = self._small_button(strings.BTN_ROT_RIGHT, lambda: self._rotate_selected(90))
        self.btn_rot_right.setIcon(rotate_icon(16, dpr, clockwise=True))
        self.btn_rot_right.setToolTip(strings.TIP_ROT_RIGHT)
        self.btn_rot_180 = self._small_button(strings.BTN_ROT_180, lambda: self._rotate_selected(180))
        self.btn_rot_180.setToolTip(strings.TIP_ROT_180)
        self.btn_rot_reset = self._small_button(strings.BTN_ROT_RESET, self._reset_selected)
        self.btn_rot_reset.setToolTip(strings.TIP_ROT_RESET)
        self._rotate_buttons = (self.btn_rot_left, self.btn_rot_right, self.btn_rot_180, self.btn_rot_reset)
        for btn in self._rotate_buttons:
            lay.addWidget(btn)

        lay.addStretch(1)
        self.lbl_count = QLabel()
        self.lbl_count.setProperty("cls", "count")
        lay.addWidget(self.lbl_count)
        return lay

    def _build_options_card(self) -> QFrame:
        card = QFrame()
        card.setProperty("cls", "card")
        grid = QGridLayout(card)
        grid.setContentsMargins(22, 16, 22, 16)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)
        grid.setColumnMinimumWidth(0, 64)
        grid.setColumnStretch(1, 1)

        self.spin_dpi = SpinBox()
        self.spin_dpi.setRange(MIN_DPI, MAX_DPI)
        self.spin_dpi.setValue(DEFAULT_DPI)
        self.spin_dpi.setSuffix(" dpi")
        self.spin_dpi.setFixedWidth(112)
        dpi_hint = QLabel(strings.DPI_HINT)
        dpi_hint.setProperty("cls", "hint")
        grid.addWidget(self._field_label(strings.FIELD_DPI), 0, 0)
        grid.addLayout(self._hrow(self.spin_dpi, dpi_hint), 0, 1)

        self.seg_out = SegmentedControl()
        self.seg_out.addSegment(strings.OUT_SAME, False)
        self.seg_out.addSegment(strings.OUT_CUSTOM, True)
        self.btn_out = self._small_button(strings.BTN_PICK_OUT, self._pick_output)
        self.lbl_out = ElidedLabel()
        self.lbl_out.setProperty("cls", "hint")
        self.seg_out.dataChanged.connect(self._update_output_controls)
        grid.addWidget(self._field_label(strings.FIELD_OUTPUT), 1, 0)
        grid.addLayout(self._hrow(self.seg_out, self.btn_out), 1, 1)
        grid.addWidget(self.lbl_out, 2, 1)
        return card

    def _build_progress_section(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(8)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(8)
        lay.addWidget(self.progress)
        self.lbl_status = ElidedLabel(strings.STATUS_IDLE, mode=Qt.ElideRight)
        self.lbl_status.setProperty("cls", "status")
        lay.addWidget(self.lbl_status)
        return lay

    def _build_actions(self) -> QHBoxLayout:
        lay = QHBoxLayout()
        lay.setSpacing(10)
        self.btn_open = QPushButton(strings.BTN_OPEN_OUTPUT)
        self.btn_open.setProperty("cls", "ghost")
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_open.clicked.connect(self._open_output)
        self.btn_open.setEnabled(False)
        lay.addWidget(self.btn_open)
        lay.addStretch(1)

        self.btn_cancel = QPushButton(strings.BTN_CANCEL)
        self.btn_cancel.setProperty("cls", "ghost")
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._cancel_export)
        self.btn_cancel.setEnabled(False)
        self.btn_start = QPushButton(strings.BTN_START)
        self.btn_start.setProperty("cls", "primary")
        self.btn_start.setCursor(Qt.PointingHandCursor)
        self.btn_start.clicked.connect(self._start_export)
        lay.addWidget(self.btn_cancel)
        lay.addWidget(self.btn_start)
        return lay

    @staticmethod
    def _small_button(text: str, slot) -> QPushButton:
        btn = QPushButton(text)
        btn.setProperty("cls", "ghostSmall")
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(slot)
        return btn

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setProperty("cls", "field")
        return label

    @staticmethod
    def _hrow(*widgets: QWidget) -> QHBoxLayout:
        """ウィジェットを左詰めで並べる行レイアウト。"""
        row = QHBoxLayout()
        row.setSpacing(8)
        for w in widgets:
            row.addWidget(w)
        row.addStretch(1)
        return row

    # -------------------------------------------------------------- 状態表示
    def _exporting(self) -> bool:
        return self._export_worker is not None

    def _loading(self) -> bool:
        return self._thumb_worker is not None or bool(self._pending)

    def _set_status(self, text: str, state: str = "") -> None:
        """状態ラベルを更新する。state は "" / "ok" / "error"。"""
        self.lbl_status.setFullText(text)
        if self.lbl_status.property("state") != state:
            self.lbl_status.setProperty("state", state)
            theme.repolish(self.lbl_status)

    def _refresh_state(self, *_args) -> None:
        """ページ数・選択状態に応じてボタンや表示を更新する。"""
        pages = self.model.rowCount()
        selected = len(self.grid.selected_rows())
        rotated = self.model.rotated_count()
        exporting = self._exporting()

        self.stack.setCurrentWidget(self.grid if (pages or self._docs) else self.drop)

        parts = [strings.COUNT_PAGES.format(n=pages)] if pages else []
        if rotated:
            parts.append(strings.COUNT_ROTATED.format(n=rotated))
        if selected:
            parts.append(strings.COUNT_SELECTED.format(n=selected))
        self.lbl_count.setText("  ・  ".join(parts))

        for btn in self._rotate_buttons:
            btn.setEnabled(bool(selected) and not exporting)
        self.btn_clear.setEnabled(bool(self._docs) and not exporting)
        # ページ数が未確定の PDF が残っている間は、書き出し対象が揃っていないので不可。
        self.btn_start.setEnabled(bool(pages) and not self._unopened and not exporting)

        if not exporting:
            if self._loading():
                self._set_status(
                    strings.STATUS_LOADING.format(done=self.model.loaded_thumbs, total=pages)
                )
            elif self.lbl_status.property("state") not in ("ok", "error"):
                self._set_status(strings.STATUS_READY if pages else strings.STATUS_IDLE)

    def _update_output_controls(self, _data: object = None) -> None:
        custom = bool(self.seg_out.currentData())
        self.btn_out.setEnabled(custom and not self._exporting())
        if custom:
            self.lbl_out.setFullText(
                strings.OUT_PREFIX.format(path=self._output_dir) if self._output_dir else ""
            )
        else:
            self.lbl_out.setFullText(strings.OUT_SAME_HINT)

    # ---------------------------------------------------------- PDF の追加
    def _pick_pdfs(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, strings.DLG_PICK_PDF, self._last_open_dir, strings.DLG_PDF_FILTER
        )
        if files:
            self._add_paths(files)

    def _add_paths(self, paths: list[str]) -> None:
        if self._exporting():
            return
        pdfs = collect_pdfs(paths)
        if not pdfs:
            QMessageBox.warning(self, APP_NAME, strings.WARN_NO_PDF)
            return
        self._last_open_dir = str(pdfs[0].parent)

        known = {_path_key(p) for p in self._docs.values()}
        skipped = 0
        for pdf in pdfs:
            key = _path_key(pdf)
            if key in known:
                skipped += 1
                continue
            known.add(key)
            doc_id = self._next_doc_id
            self._next_doc_id += 1
            self._docs[doc_id] = pdf
            self._unopened.add(doc_id)
            self._pending.append((doc_id, pdf))

        if self.lbl_status.property("state"):
            self._set_status("")  # 前回の完了/エラー表示を消す
        self._start_thumbnail_worker()
        self._refresh_state()
        if skipped:
            QMessageBox.information(self, APP_NAME, strings.WARN_DUPLICATE.format(n=skipped))

    def _start_thumbnail_worker(self) -> None:
        if self._thumb_worker is not None or not self._pending:
            return
        jobs, self._pending = self._pending, []
        worker = ThumbnailWorker(jobs)
        worker.opened.connect(self._on_doc_opened)
        worker.openFailed.connect(self._on_doc_failed)
        worker.thumbnail.connect(self._on_thumbnail)
        worker.finished.connect(self._on_thumb_thread_finished)
        self._thumb_worker = worker
        worker.start()

    def _on_doc_opened(self, doc_id: int, page_count: int) -> None:
        path = self._docs.get(doc_id)
        if path is None:
            return  # クリア済み
        self._unopened.discard(doc_id)
        self.model.add_document(doc_id, path, page_count)
        if self.model.rowCount() == page_count and not self.grid.selected_rows():
            self.grid.select_row(0)
            self.grid.setFocus()
        self._refresh_state()

    def _on_doc_failed(self, doc_id: int, message: str) -> None:
        path = self._docs.pop(doc_id, None)
        if path is None:
            return
        self._unopened.discard(doc_id)
        self._load_errors.append(f"・{path.name}: {message}")
        self._refresh_state()

    def _on_thumbnail(self, doc_id: int, page_index: int, image) -> None:
        self.model.set_thumbnail(doc_id, page_index, image)

    def _on_thumb_thread_finished(self) -> None:
        self._thumb_worker = None
        if self._pending:
            self._start_thumbnail_worker()
        elif self._load_errors:
            items = "\n".join(self._load_errors[:15])
            if len(self._load_errors) > 15:
                items += "\n" + strings.SUMMARY_MORE.format(n=len(self._load_errors) - 15)
            self._load_errors.clear()
            QMessageBox.warning(self, APP_NAME, strings.WARN_LOAD_FAILED.format(items=items))
        self._refresh_state()

    def _clear(self) -> None:
        if self._exporting() or not self._docs:
            return
        if self.model.rotated_count():
            ret = QMessageBox.question(self, APP_NAME, strings.CONFIRM_CLEAR, QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
        if self._thumb_worker is not None:
            # 停止を待たない。以後の通知は doc_id が消えているので無視される。
            self._thumb_worker.cancel()
        self._pending.clear()
        self._docs.clear()
        self._unopened.clear()
        self._load_errors.clear()
        self.model.clear()
        self._set_status(strings.STATUS_IDLE)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._refresh_state()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if not self._exporting() and dropped_local_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = dropped_local_paths(event)
        if paths and not self._exporting():
            event.acceptProposedAction()
            self._add_paths(paths)

    # ---------------------------------------------------------------- 回転
    def _rotate_selected(self, delta: int) -> None:
        if self._exporting():
            return
        self.model.rotate(self.grid.selected_rows(), delta)

    def _reset_selected(self) -> None:
        if self._exporting():
            return
        self.model.reset_rotation(self.grid.selected_rows())

    def _open_preview(self, row: int) -> None:
        if self._exporting() or not 0 <= row < self.model.rowCount():
            return
        dialog = PreviewDialog(self.model, row, self)
        dialog.exec()
        self.grid.select_row(dialog.current_row())
        self.grid.setFocus()

    def _show_context_menu(self, pos: QPoint) -> None:
        if self._exporting() or not self.model.rowCount():
            return
        index = self.grid.indexAt(pos)
        if index.isValid() and index.row() not in self.grid.selected_rows():
            self.grid.select_row(index.row())
        has_sel = bool(self.grid.selected_rows())

        menu = QMenu(self)
        act_preview = menu.addAction(strings.MENU_PREVIEW)
        act_preview.setEnabled(index.isValid())
        menu.addSeparator()
        actions = {
            menu.addAction(strings.BTN_ROT_LEFT): lambda: self._rotate_selected(-90),
            menu.addAction(strings.BTN_ROT_RIGHT): lambda: self._rotate_selected(90),
            menu.addAction(strings.BTN_ROT_180): lambda: self._rotate_selected(180),
            menu.addAction(strings.BTN_ROT_RESET): self._reset_selected,
        }
        for act in actions:
            act.setEnabled(has_sel)
        menu.addSeparator()
        act_all = menu.addAction(strings.MENU_SELECT_ALL)

        chosen = menu.exec(self.grid.viewport().mapToGlobal(pos))
        if chosen is act_preview:
            self._open_preview(index.row())
        elif chosen is act_all:
            self.grid.selectAll()
        elif chosen in actions:
            actions[chosen]()

    # -------------------------------------------------------------- 出力先
    def _pick_output(self) -> None:
        start = str(self._output_dir) if self._output_dir else self._last_open_dir
        folder = QFileDialog.getExistingDirectory(self, strings.DLG_PICK_OUTPUT, start)
        if folder:
            self._output_dir = Path(folder)
            self._update_output_controls()

    def _open_output(self) -> None:
        if self._last_output and self._last_output.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_output)))

    # ---------------------------------------------------------------- 書き出し
    def _build_options(self) -> ExportOptions:
        out_dir = self._output_dir if bool(self.seg_out.currentData()) else None
        return ExportOptions(dpi=self.spin_dpi.value(), output_dir=out_dir).validated()

    def _set_running(self, running: bool) -> None:
        for w in self._lockable:
            w.setEnabled(not running)
        self.btn_cancel.setEnabled(running)
        if not running:
            self._update_output_controls()
        self._refresh_state()

    def _start_export(self) -> None:
        if not self.model.rowCount():
            QMessageBox.warning(self, APP_NAME, strings.WARN_NO_PAGES)
            return
        if bool(self.seg_out.currentData()) and not self._output_dir:
            QMessageBox.warning(self, APP_NAME, strings.WARN_NO_OUTPUT)
            return
        try:
            options = self._build_options()
        except ValueError as e:
            QMessageBox.warning(self, APP_NAME, str(e))
            return

        self.btn_open.setEnabled(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._set_status(strings.STATUS_STARTED)

        worker = ExportWorker(self.model.page_items(), options)
        worker.progress.connect(self._on_export_progress)
        worker.status.connect(self._set_status)
        worker.completed.connect(self._on_export_completed)
        worker.failed.connect(self._on_export_failed)
        worker.finished.connect(self._on_export_thread_finished)
        self._export_worker = worker
        self._set_running(True)
        worker.start()

    def _cancel_export(self) -> None:
        if self._export_worker:
            self._export_worker.cancel()
            self.btn_cancel.setEnabled(False)
            self._set_status(strings.STATUS_CANCELLING)

    def _on_export_progress(self, done: int, total: int, name: str) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)
        if name:
            self._set_status(strings.STATUS_PROGRESS.format(done=done, total=total, name=name))

    def _on_export_completed(self, result: ExportResult) -> None:
        self.progress.setValue(self.progress.maximum())
        dirs = result.output_dirs
        if dirs:
            # 複数 PDF をまとめて書き出した場合は共通の親フォルダを開く。
            self._last_output = dirs[0] if len(dirs) == 1 else Path(os.path.commonpath([str(d) for d in dirs]))
            self.btn_open.setEnabled(True)

        if result.cancelled:
            self._set_status(strings.STATUS_CANCELLED.format(n=result.file_count))
        elif result.errors:
            self._set_status(strings.STATUS_DONE.format(n=result.file_count), state="error")
        else:
            self._set_status(strings.STATUS_DONE.format(n=result.file_count), state="ok")
        self._show_summary(result)

    def _show_summary(self, result: ExportResult) -> None:
        lines: list[str] = []
        if result.cancelled:
            lines.append(strings.SUMMARY_CANCELLED)
        lines.append(strings.SUMMARY_DONE.format(n=result.file_count))
        if result.output_dirs:
            lines += ["", strings.SUMMARY_DIRS]
            lines += [f"・{d}" for d in result.output_dirs[:10]]
            if len(result.output_dirs) > 10:
                lines.append(strings.SUMMARY_MORE.format(n=len(result.output_dirs) - 10))
        if result.errors:
            lines += ["", strings.SUMMARY_ERRORS.format(n=len(result.errors))]
            lines += [f"・{m}" for m in result.errors[:10]]
            if len(result.errors) > 10:
                lines.append(strings.SUMMARY_MORE.format(n=len(result.errors) - 10))

        box = QMessageBox(self)
        box.setWindowTitle(APP_NAME)
        box.setIcon(QMessageBox.Warning if result.errors else QMessageBox.Information)
        box.setText("\n".join(lines))
        box.exec()

    def _on_export_failed(self, message: str) -> None:
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self._set_status(strings.STATUS_ERROR, state="error")
        QMessageBox.critical(self, APP_NAME, strings.ERROR_DIALOG.format(message=message))

    def _on_export_thread_finished(self) -> None:
        self._export_worker = None
        self._set_running(False)

    # ---------------------------------------------------------- settings I/O
    def _restore_settings(self) -> None:
        s = load_settings()
        self.spin_dpi.setValue(max(MIN_DPI, min(MAX_DPI, s.dpi)))
        if s.output_dir and Path(s.output_dir).is_dir():
            self._output_dir = Path(s.output_dir)
        self.seg_out.setCurrentData(bool(s.use_custom_output and self._output_dir))
        if s.last_open_dir and Path(s.last_open_dir).is_dir():
            self._last_open_dir = s.last_open_dir
        self._update_output_controls()

    def _current_settings(self) -> Settings:
        return Settings(
            dpi=self.spin_dpi.value(),
            use_custom_output=bool(self.seg_out.currentData()),
            output_dir=str(self._output_dir) if self._output_dir else None,
            last_open_dir=self._last_open_dir or None,
        )

    def closeEvent(self, event) -> None:  # noqa: N802
        if self._export_worker and self._export_worker.isRunning():
            ret = QMessageBox.question(self, APP_NAME, strings.CONFIRM_EXIT, QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                event.ignore()
                return
            self._export_worker.cancel()
            # キャンセルはページの区切りで効く。QThread は走行中に破棄すると
            # 異常終了するため、完全に止まるまで待つ。
            if not self._export_worker.wait(5000):
                self._set_status(strings.STATUS_CLOSING)
                self._export_worker.wait()

        if self._thumb_worker and self._thumb_worker.isRunning():
            self._thumb_worker.cancel()
            self._thumb_worker.wait()

        save_settings(self._current_settings())
        super().closeEvent(event)
