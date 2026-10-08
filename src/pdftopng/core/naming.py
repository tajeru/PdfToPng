"""出力フォルダ・ファイル名の決定（上書き回避）。"""
from __future__ import annotations

from pathlib import Path

MIN_DIGITS = 3


def page_filename(stem: str, page_number: int, page_count: int) -> str:
    """`<stem>_001.png` 形式のファイル名。桁数はページ数に合わせる（最低 3 桁）。

    page_number は 1 始まり。
    """
    width = max(MIN_DIGITS, len(str(page_count)))
    return f"{stem}_{page_number:0{width}d}.png"


def unique_dir(base: Path) -> Path:
    """base が存在しなければ base、存在すれば base_1, base_2 … の空き名を返す。"""
    base = Path(base)
    if not base.exists():
        return base
    n = 1
    while True:
        candidate = base.with_name(f"{base.name}_{n}")
        if not candidate.exists():
            return candidate
        n += 1


def create_output_dir(pdf_path: Path, output_root: Path | None = None) -> Path:
    """PDF 用の出力フォルダを新規作成して返す。

    既定は「PDF と同じ場所に PDF 名のフォルダ」。output_root 指定時はその直下。
    既存フォルダは使わず、必ず新しいフォルダを作る（上書き防止）。
    """
    pdf_path = Path(pdf_path)
    root = Path(output_root) if output_root else pdf_path.parent
    base = root / pdf_path.stem
    while True:
        target = unique_dir(base)
        try:
            target.mkdir(parents=True, exist_ok=False)
            return target
        except FileExistsError:
            # 判定から作成までの間に他で作られた場合は次の候補へ。
            continue
