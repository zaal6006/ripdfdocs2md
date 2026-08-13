import pymupdf
import pytest

from ripdfdocs2md._pdf_checkbox_worker import annotate_checkboxes, find_checkboxes


def _draw_line_border(page, x0, y0, x1, y1, color=(0, 0, 0)):
    """A checkbox border drawn as a native stroked rectangle ("re") —
    the reliable way to construct one in a test fixture. (The real-world
    example this detector was validated against instead builds its
    border from several separate line ("l") segments in one drawing
    object; _has_border_outline handles that case too, but PyMuPDF's own
    Shape API collapses a closed line-segment rectangle into a single
    "qu" quad rather than "l" segments, so it can't be exercised cleanly
    from a synthetic fixture the same way.)"""
    page.draw_rect(pymupdf.Rect(x0, y0, x1, y1), color=color, fill=None, width=1)


def _draw_x_mark(page, x0, y0, x1, y1, color=(0, 0, 0)):
    """An "X" checked-mark, as one combined drawing object (its two
    diagonal strokes)."""
    shape = page.new_shape()
    shape.draw_line((x0, y0), (x1, y1))
    shape.draw_line((x1, y0), (x0, y1))
    shape.finish(color=color, fill=None, width=1)
    shape.commit()


@pytest.fixture
def checkbox_pdf(tmp_path):
    """A page with three checkbox+label pairs (unchecked, checked via an
    X, unchecked) laid out like the validated real-world example, plus a
    decorative graphic with no nearby label that must not be mistaken
    for a checkbox."""
    doc = pymupdf.open()
    page = doc.new_page()

    _draw_line_border(page, 100, 100, 110, 110)
    page.insert_text((112, 108), "New", fontsize=10, fontname="helv")

    _draw_line_border(page, 160, 100, 170, 110)
    _draw_x_mark(page, 160, 100, 170, 110)
    page.insert_text((172, 108), "Revised", fontsize=10, fontname="helv")

    _draw_line_border(page, 240, 100, 250, 110)
    page.insert_text((252, 108), "Reviewed", fontsize=10, fontname="helv")

    # decorative graphic: same size/shape, no label anywhere nearby
    _draw_line_border(page, 300, 300, 310, 310)

    path = tmp_path / "checkboxes.pdf"
    doc.save(path)
    return str(path)


def test_detects_unchecked_and_checked_boxes(checkbox_pdf):
    doc = pymupdf.open(checkbox_pdf)
    boxes = find_checkboxes(doc[0])

    form_boxes = [(r, c) for r, c in boxes if r.x0 < 290]  # excludes the decorative shape
    assert len(form_boxes) == 3
    checked_states = {round(r.x0): checked for r, checked in form_boxes}
    assert checked_states[100] is False  # "New"
    assert checked_states[160] is True  # "Revised" (has the X)
    assert checked_states[240] is False  # "Reviewed"


def test_rejects_decorative_shape_with_no_nearby_label(checkbox_pdf):
    doc = pymupdf.open(checkbox_pdf)
    boxes = find_checkboxes(doc[0])
    rects = [r for r, _ in boxes]
    assert not any(290 <= r.x0 <= 320 for r in rects)


@pytest.fixture
def native_rect_checkbox_pdf(tmp_path):
    """A checkbox border drawn as a single native stroked rectangle
    ('re' item) rather than four separate line segments — a different,
    equally common way PDF tools draw a box."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(100, 100, 112, 112), color=(0, 0, 0), fill=None, width=1)
    page.insert_text((114, 110), "Yes", fontsize=10, fontname="helv")
    path = tmp_path / "native_rect.pdf"
    doc.save(path)
    return str(path)


def test_detects_checkbox_drawn_as_native_rectangle(native_rect_checkbox_pdf):
    doc = pymupdf.open(native_rect_checkbox_pdf)
    boxes = find_checkboxes(doc[0])
    assert len(boxes) == 1
    assert boxes[0][1] is False


@pytest.fixture
def colorful_icon_pdf(tmp_path):
    """A checkbox-shaped, checkbox-sized graphic with a vivid (non-black)
    fill next to ordinary text — a decorative icon/badge, not a form
    checkbox, and must not be mistaken for one."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.draw_rect(pymupdf.Rect(100, 100, 112, 112), color=None, fill=(1.0, 0.3, 0.5))
    page.insert_text((114, 110), "Some label", fontsize=10, fontname="helv")
    path = tmp_path / "colorful_icon.pdf"
    doc.save(path)
    return str(path)


def test_rejects_colorful_non_checkbox_graphic(colorful_icon_pdf):
    doc = pymupdf.open(colorful_icon_pdf)
    assert find_checkboxes(doc[0]) == []


@pytest.fixture
def bold_heading_decoration_pdf(tmp_path):
    """A small checkbox-shaped graphic sitting only next to bold heading
    text — the pattern behind a real false positive we found (a
    decorative accent within a document's stylized heading font)."""
    doc = pymupdf.open()
    page = doc.new_page()
    _draw_line_border(page, 100, 100, 110, 110)
    page.insert_text((112, 108), "A Bold Heading", fontsize=12, fontname="hebo")
    path = tmp_path / "bold_heading.pdf"
    doc.save(path)
    return str(path)


def test_rejects_shape_next_to_only_bold_text(bold_heading_decoration_pdf):
    doc = pymupdf.open(bold_heading_decoration_pdf)
    assert find_checkboxes(doc[0]) == []


def test_annotate_checkboxes_burns_correct_text_into_copy(checkbox_pdf, tmp_path):
    output_path = tmp_path / "annotated.pdf"
    count = annotate_checkboxes(checkbox_pdf, str(output_path))

    assert count == 3
    assert output_path.exists()

    annotated = pymupdf.open(str(output_path))
    text = annotated[0].get_text()
    assert "[ ]" in text
    assert "[x]" in text
    assert "New" in text
    assert "Revised" in text
    assert "Reviewed" in text
