"""ページ群を PNG として書き出す（レンダリング → 回転 → 保存）。

1 ページずつ処理して保存後すぐ解放するので、高 DPI でもメモリを圧迫しない。
PDF 単位のエラー（開けない等）やページ単位のエラーは記録して処理を続ける。
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from ..config import ExportOptions
from ..logging_setup import get_logger
from . import rotation
from .document import PageItem, PdfFile, PdfOpenError
from .naming import create_output_dir, page_filename

log = get_logger(__name__)

ProgressFn = Callable[[int, int, str], None]  # done, total, current_name
StatusFn = Callable[[str], None]
CancelFn = Callable[[], bool]


@dataclass
class PdfExportResult:
    pdf_path: Path
    output_dir: Path | None = None
    files: list[Path] = field(default_factory=list)
    error: str | None = None  # PDF 単位の失敗（開けない・フォルダを作れない）
    page_errors: list[str] = field(default_factory=list)


@dataclass
class ExportResult:
    results: list[PdfExportResult] = field(default_factory=list)
    cancelled: bool = False

    @property
    def file_count(self) -> int:
        return sum(len(r.files) for r in self.results)

    @property
    def output_dirs(self) -> list[Path]:
        return [r.output_dir for r in self.results if r.output_dir is not None]

    @property
    def errors(self) -> list[str]:
        messages: list[str] = []
        for r in self.results:
            if r.error:
                messages.append(f"{r.pdf_path.name}: {r.error}")
            messages.extend(f"{r.pdf_path.name}: {m}" for m in r.page_errors)
        return messages


def group_pages(pages: Iterable[PageItem]) -> list[tuple[Path, list[PageItem]]]:
    """PDF ごとにまとめる（最初に現れた順を保つ）。"""
    groups: dict[Path, list[PageItem]] = {}
    for item in pages:
        groups.setdefault(Path(item.pdf_path), []).append(item)
    return list(groups.items())


def export(
    pages: Iterable[PageItem],
    options: ExportOptions,
    *,
    on_progress: ProgressFn | None = None,
    on_status: StatusFn | None = None,
    should_cancel: CancelFn | None = None,
) -> ExportResult:
    options = options.validated()
    groups = group_pages(pages)
    total = sum(len(items) for _, items in groups)
    done = 0
    result = ExportResult()

    def progress(name: str = "") -> None:
        if on_progress:
            on_progress(done, total, name)

    def cancelled() -> bool:
        return bool(should_cancel and should_cancel())

    progress()
    for pdf_path, items in groups:
        if cancelled():
            result.cancelled = True
            break
        r = PdfExportResult(pdf_path=pdf_path)
        result.results.append(r)
        if on_status:
            on_status(f"{pdf_path.name} を書き出し中…")

        try:
            pdf = PdfFile(pdf_path)
        except PdfOpenError as e:
            r.error = str(e)
            done += len(items)
            progress()
            continue

        with pdf:
            try:
                r.output_dir = create_output_dir(pdf_path, options.output_dir)
            except OSError as e:
                r.error = f"出力フォルダを作成できません（{e.strerror or e}）。"
                done += len(items)
                progress()
                continue

            for item in items:
                if cancelled():
                    result.cancelled = True
                    break
                name = page_filename(pdf_path.stem, item.page_index + 1, pdf.page_count)
                dest = r.output_dir / name
                try:
                    image = pdf.render_dpi(item.page_index, options.dpi)
                    image = rotation.apply(image, item.rotation)
                    image.save(dest, format="PNG", dpi=(options.dpi, options.dpi))
                    r.files.append(dest)
                except Exception as e:  # noqa: BLE001 - 1 ページの失敗で全体を止めない
                    log.exception("ページの書き出しに失敗: %s", dest)
                    r.page_errors.append(f"{name}: {e}")
                done += 1
                progress(name)

        if result.cancelled:
            break
    return result
