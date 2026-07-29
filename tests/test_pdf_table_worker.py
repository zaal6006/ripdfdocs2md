import pymupdf
import pytest

from ripdfdocs2md._pdf_table_worker import extract_tables


def _thin_rect(x0, y0, x1, y1):
    return pymupdf.Rect(x0, y0, x1, y1)


@pytest.fixture
def mixed_table_pdf(tmp_path):
    """A 3-row table mirroring the real-world pattern that broke naive
    table detection: rows 0 and 1 are genuinely 2 columns, each with its
    OWN divider at a slightly different x (as office-generated PDFs often
    draw them per-row rather than as one continuous line); row 2 is a
    genuine single-column span with no divider at all."""
    doc = pymupdf.open()
    page = doc.new_page(width=500, height=300)

    page.draw_rect(_thin_rect(100, 100, 100.5, 220), color=None, fill=(0, 0, 0))
    page.draw_rect(_thin_rect(399.5, 100, 400, 220), color=None, fill=(0, 0, 0))
    for y in (100, 140, 180, 220):
        page.draw_rect(_thin_rect(100, y, 400, y + 0.5), color=None, fill=(0, 0, 0))
    page.draw_rect(_thin_rect(250, 100, 250.5, 140), color=None, fill=(0, 0, 0))  # row0 divider
    page.draw_rect(_thin_rect(280, 140, 280.5, 180), color=None, fill=(0, 0, 0))  # row1 divider, different x

    page.insert_text((110, 120), "Left0", fontsize=10)
    page.insert_text((260, 120), "Right0", fontsize=10)
    page.insert_text((110, 160), "Left1", fontsize=10)
    page.insert_text((290, 160), "Right1", fontsize=10)
    page.insert_text((110, 200), "Merged row full width", fontsize=10)

    path = tmp_path / "mixed_table.pdf"
    doc.save(path)
    return str(path)


def test_reconstructs_per_row_dividers_and_merged_row(mixed_table_pdf):
    pages = extract_tables(mixed_table_pdf, [[]])

    assert len(pages) == 1
    tables = pages[0]
    assert len(tables) == 1
    rows = tables[0]["rows"]

    assert rows[0] == ["Left0", "Right0"]
    assert rows[1] == ["Left1", "Right1"]
    assert rows[2][0] == "Merged row full width"
    assert rows[2][1] == ""


def test_uses_ml_layout_bbox_when_provided(mixed_table_pdf):
    ml_page_boxes = [{"class": "table", "bbox": [100, 100, 400, 220.5]}]
    pages = extract_tables(mixed_table_pdf, [ml_page_boxes])

    assert len(pages[0]) == 1
    rows = pages[0][0]["rows"]
    assert rows[0] == ["Left0", "Right0"]
    assert rows[2][0] == "Merged row full width"


@pytest.fixture
def no_ruling_lines_pdf(tmp_path):
    """A page with plain text and no thin ruling rectangles at all."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Just a normal paragraph, no table here.", fontsize=11)
    path = tmp_path / "plain.pdf"
    doc.save(path)
    return str(path)


def test_no_tables_found_on_plain_page(no_ruling_lines_pdf):
    pages = extract_tables(no_ruling_lines_pdf, [[]])
    assert pages == [[]]
