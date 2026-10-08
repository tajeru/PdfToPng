from pdftopng.core.naming import create_output_dir, page_filename, unique_dir


def test_page_filename_min_three_digits():
    assert page_filename("scan", 1, 9) == "scan_001.png"
    assert page_filename("scan", 12, 120) == "scan_012.png"


def test_page_filename_widens_for_many_pages():
    assert page_filename("scan", 7, 1200) == "scan_0007.png"


def test_unique_dir(tmp_path):
    base = tmp_path / "doc"
    assert unique_dir(base) == base
    base.mkdir()
    assert unique_dir(base) == tmp_path / "doc_1"
    (tmp_path / "doc_1").mkdir()
    assert unique_dir(base) == tmp_path / "doc_2"


def test_create_output_dir_next_to_pdf(tmp_path):
    pdf = tmp_path / "スキャン 1.pdf"
    first = create_output_dir(pdf)
    second = create_output_dir(pdf)
    assert first == tmp_path / "スキャン 1"
    assert second == tmp_path / "スキャン 1_1"
    assert first.is_dir() and second.is_dir()


def test_create_output_dir_custom_root(tmp_path):
    pdf = tmp_path / "in" / "a.pdf"
    out = create_output_dir(pdf, tmp_path / "out")
    assert out == tmp_path / "out" / "a"
    assert out.is_dir()
