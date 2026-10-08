import pytest
from conftest import MARK, is_red

from pdftopng.core.document import PdfFile, PdfOpenError, collect_pdfs


def test_page_count_and_render_size(make_pdf, tmp_path):
    pdf_path = make_pdf(tmp_path / "a.pdf", [(100, 150), (200, 120)])
    with PdfFile(pdf_path) as pdf:
        assert pdf.page_count == 2
        img = pdf.render_dpi(0, 144)  # 72pt 基準なので 2 倍
        assert abs(img.width - 200) <= 1 and abs(img.height - 300) <= 1
        assert img.mode == "RGB"
        assert is_red(img.getpixel((MARK, MARK)))  # 2 倍なので目印も 60px


def test_render_fit_longest_side(make_pdf, tmp_path):
    pdf_path = make_pdf(tmp_path / "a.pdf", [(200, 120)])
    with PdfFile(pdf_path) as pdf:
        img = pdf.render_fit(0, 100)
    assert abs(max(img.size) - 100) <= 1
    assert img.width > img.height


def test_render_out_of_range(make_pdf, tmp_path):
    with PdfFile(make_pdf(tmp_path / "a.pdf")) as pdf:
        with pytest.raises(IndexError):
            pdf.render(5, 1.0)


def test_japanese_path(make_pdf, tmp_path):
    pdf_path = make_pdf(tmp_path / "日本語 フォルダ" / "スキャン（1）.pdf", [(100, 150)] * 3)
    with PdfFile(pdf_path) as pdf:
        assert pdf.page_count == 3


def test_broken_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"this is not a pdf")
    with pytest.raises(PdfOpenError):
        PdfFile(bad)


def test_missing_file(tmp_path):
    with pytest.raises(PdfOpenError):
        PdfFile(tmp_path / "none.pdf")


def test_password_protected(make_pdf, tmp_path):
    pypdf = pytest.importorskip("pypdf")
    src = make_pdf(tmp_path / "plain.pdf")
    writer = pypdf.PdfWriter(clone_from=str(src))
    writer.encrypt("secret", algorithm="RC4-128")
    locked = tmp_path / "locked.pdf"
    with locked.open("wb") as f:
        writer.write(f)
    with pytest.raises(PdfOpenError, match="パスワード"):
        PdfFile(locked)


def test_collect_pdfs(tmp_path, make_pdf):
    folder = tmp_path / "dir"
    for name in ("10.pdf", "2.pdf", "1.PDF"):
        make_pdf(folder / name)
    (folder / "note.txt").write_text("x")
    make_pdf(folder / "sub" / "deep.pdf")  # サブフォルダは対象外
    single = make_pdf(tmp_path / "z.pdf")

    result = collect_pdfs([str(single), str(folder), str(tmp_path / "note.txt")])
    assert [p.name for p in result] == ["z.pdf", "1.PDF", "2.pdf", "10.pdf"]
