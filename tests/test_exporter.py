from conftest import MARK, is_red
from PIL import Image

from pdftopng.config import ExportOptions
from pdftopng.core.document import PageItem
from pdftopng.core.exporter import export


def _pages(pdf, count, rotations=None):
    rotations = rotations or [0] * count
    return [PageItem(pdf, i, rotations[i]) for i in range(count)]


def test_export_writes_numbered_pngs(make_pdf, tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf", [(100, 150)] * 3)
    result = export(_pages(pdf, 3), ExportOptions(dpi=72))

    out = tmp_path / "scan"
    assert result.output_dirs == [out]
    assert [p.name for p in result.results[0].files] == ["scan_001.png", "scan_002.png", "scan_003.png"]
    assert result.file_count == 3
    assert not result.errors and not result.cancelled
    with Image.open(out / "scan_001.png") as img:
        assert abs(img.width - 100) <= 1 and abs(img.height - 150) <= 1
        assert round(img.info["dpi"][0]) == 72


def test_export_applies_rotation(make_pdf, tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf", [(100, 150)] * 3)
    result = export(_pages(pdf, 3, [90, 180, 270]), ExportOptions(dpi=72))
    files = result.results[0].files
    c = MARK // 2

    with Image.open(files[0]) as img:  # 時計回り 90°: 目印は右上
        assert img.width > img.height
        assert is_red(img.getpixel((img.width - c, c)))
    with Image.open(files[1]) as img:  # 180°: 右下
        assert img.height > img.width
        assert is_red(img.getpixel((img.width - c, img.height - c)))
    with Image.open(files[2]) as img:  # 270°: 左下
        assert img.width > img.height
        assert is_red(img.getpixel((c, img.height - c)))


def test_export_does_not_overwrite(make_pdf, tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf")
    first = export(_pages(pdf, 1), ExportOptions(dpi=72))
    second = export(_pages(pdf, 1), ExportOptions(dpi=72))
    assert first.output_dirs == [tmp_path / "scan"]
    assert second.output_dirs == [tmp_path / "scan_1"]
    assert pdf.is_file()  # 元 PDF はそのまま


def test_export_custom_output_dir(make_pdf, tmp_path):
    pdf = make_pdf(tmp_path / "in" / "scan.pdf")
    result = export(_pages(pdf, 1), ExportOptions(dpi=72, output_dir=tmp_path / "out"))
    assert result.output_dirs == [tmp_path / "out" / "scan"]
    assert (tmp_path / "out" / "scan" / "scan_001.png").is_file()


def test_export_continues_after_broken_pdf(make_pdf, tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"broken")
    good = make_pdf(tmp_path / "good.pdf", [(100, 150)] * 2)
    pages = [PageItem(bad, 0), *_pages(good, 2)]

    progress = []
    result = export(pages, ExportOptions(dpi=72), on_progress=lambda d, t, n: progress.append((d, t)))
    assert result.file_count == 2
    assert len(result.errors) == 1 and "bad.pdf" in result.errors[0]
    assert progress[-1] == (3, 3)


def test_export_cancel(make_pdf, tmp_path):
    pdf = make_pdf(tmp_path / "scan.pdf", [(100, 150)] * 5)
    calls = {"n": 0}

    def should_cancel():
        calls["n"] += 1
        return calls["n"] > 3  # 数ページ処理したところで中断

    result = export(_pages(pdf, 5), ExportOptions(dpi=72), should_cancel=should_cancel)
    assert result.cancelled
    assert 0 < result.file_count < 5


def test_invalid_dpi_raises(make_pdf, tmp_path):
    import pytest

    pdf = make_pdf(tmp_path / "scan.pdf")
    with pytest.raises(ValueError):
        export(_pages(pdf, 1), ExportOptions(dpi=10))
