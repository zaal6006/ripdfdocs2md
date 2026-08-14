import pymupdf
import pytest
from docx import Document

from ripdfdocs2md.cli import main


def _make_pdf(path):
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello from a test PDF.", fontsize=12)
    doc.save(path)


def _make_docx(path):
    doc = Document()
    doc.add_paragraph("Hello from a test DOCX.")
    doc.save(path)


def test_converts_single_pdf_file(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    _make_pdf(pdf_path)
    out_dir = tmp_path / "output"

    exit_code = main([str(pdf_path), "-o", str(out_dir)])

    assert exit_code == 0
    md_path = out_dir / "report.md"
    assert md_path.exists()
    assert "Hello from a test PDF" in md_path.read_text(encoding="utf-8")


def test_converts_whole_folder(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _make_pdf(input_dir / "a.pdf")
    _make_docx(input_dir / "b.docx")
    out_dir = tmp_path / "output"

    exit_code = main([str(input_dir), "-o", str(out_dir)])

    assert exit_code == 0
    assert (out_dir / "a.md").exists()
    assert (out_dir / "b.md").exists()


def test_same_stem_different_extension_gets_numeric_suffix(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    _make_pdf(input_dir / "report.pdf")
    _make_docx(input_dir / "report.docx")
    out_dir = tmp_path / "output"

    main([str(input_dir), "-o", str(out_dir)])

    assert (out_dir / "report.md").exists()
    assert (out_dir / "report_1.md").exists()


def test_doc_file_fails_with_nonzero_exit_when_soffice_unavailable(tmp_path, monkeypatch):
    # Forcing RIPDFDOCS2MD_SOFFICE to a nonexistent path makes this
    # deterministic regardless of whether the machine running this test
    # actually has LibreOffice installed (unlike garbage .doc *content*,
    # which LibreOffice's own format auto-detection can be permissive
    # enough to still parse as plain text rather than failing).
    monkeypatch.setenv("RIPDFDOCS2MD_SOFFICE", str(tmp_path / "nonexistent-soffice.exe"))
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "legacy.doc").write_bytes(b"not a real doc file")
    out_dir = tmp_path / "output"

    exit_code = main([str(input_dir), "-o", str(out_dir)])

    assert exit_code == 1
    assert not (out_dir / "legacy.md").exists()


def test_images_off_by_default(tmp_path):
    pdf_path = tmp_path / "report.pdf"
    _make_pdf(pdf_path)
    out_dir = tmp_path / "output"

    main([str(pdf_path), "-o", str(out_dir)])

    assert not (out_dir / "report_assets").exists()


def test_no_files_found_returns_error(tmp_path):
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()

    exit_code = main([str(empty_dir)])

    assert exit_code == 1


def test_summary_reports_zero_failures_on_clean_run(tmp_path, capsys):
    pdf_path = tmp_path / "report.pdf"
    _make_pdf(pdf_path)
    out_dir = tmp_path / "output"

    main([str(pdf_path), "-o", str(out_dir)])

    output = capsys.readouterr().out
    assert "1 converted, 0 failed, 0 skipped" in output
