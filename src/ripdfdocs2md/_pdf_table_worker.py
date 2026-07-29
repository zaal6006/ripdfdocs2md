"""Standalone worker: extract tables from a PDF using plain PyMuPDF.

Runs as a separate process (see pdf_reader.py) so it never shares a
process with pymupdf4llm. pymupdf4llm's ML layout mode (on by default)
monkey-patches PyMuPDF's table detection and text-spacing reconstruction
process-wide, and toggling it back off mid-process does not fully undo
that — this worker needs the original, unpatched PyMuPDF behavior, and
the only reliable way to get that is a process that never imported
pymupdf4llm in the first place.

Two independent things can go wrong with a table on a page:

1. pymupdf4llm's ML layout model classifies the region as "table" (right
   call — usually its bbox is the most complete one), but its own
   table-to-text rendering is wrong for irregular/merged cells: a wrapped
   two-line label like "Canada except in Northern territories" can get
   rendered as if each line were a separate row.
2. The ML model misclassifies the region as "text" (or something else)
   entirely, flattening a real table into one run-on paragraph. PyMuPDF's
   own `page.find_tables()` (rule-based, looks for ruling lines) usually
   still finds these — but its own bbox can itself be incomplete (it can
   miss a row that lacks a clean full-width ruling line PyMuPDF is happy
   with; the ML model's bbox for the same region has been observed to be
   the more complete one in that case too).

So this worker takes the *union* of both signals — page_boxes entries
already classified "table" by the caller (see pdf_reader.py, which passes
them in via stdin as JSON), plus any additional page.find_tables() region
not already covered by one of those — and rebuilds the grid for each
region ourselves from the underlying vector rectangles, rather than
trusting either engine's own cell-assignment:

Thin, (nearly) full-width rectangles are row borders; thin, tall
rectangles strictly inside the region are that row's own column
divider(s) (if it has one — a row can be a genuine single-column span
with no divider at all, which is drawn correctly by leaving it out).
Every text line is then assigned to a row by its y-position and a column
by which side of that row's divider(s) it falls on. If a region has none
of these ruling rectangles at all (e.g. borders drawn as line strokes
instead), we fall back to PyMuPDF's own `Table.extract()` if a
find_tables() result overlaps it, otherwise it's left alone.

Reads page_boxes (one list per page, or an empty list) as a JSON array on
stdin. Prints one JSON list to stdout: one entry per page, each a list of
tables found on that page as {"bbox": [x0, y0, x1, y1], "rows": [[...]]}.
"""

import bisect
import json
import sys

import pymupdf

from .pdf_tables import _overlap_fraction

MIN_TABLE_ROWS = 2
MIN_TABLE_COLS = 2

MIN_ROW_RULE_WIDTH_FRACTION = 0.85
MIN_COLUMN_RULE_OVERLAP_FRACTION = 0.6
THIN_RECT_MAX_THICKNESS = 1.2
MIN_VERTICAL_RULE_HEIGHT = 5.0
ROW_BOUNDARY_Y_TOLERANCE = 1.5
LINE_GROUP_Y_TOLERANCE = 4.0
CANDIDATE_OVERLAP_THRESHOLD = 0.5


def _thin_rects_in_bbox(page, bbox):
    """Split the thin filled rectangles inside `bbox` into candidate row
    borders (near-full-width, flat) and candidate column dividers
    (tall, narrow, and not the region's own outer left/right border)."""
    x0, y0, x1, y1 = bbox
    horizontal, vertical = [], []
    for drawing in page.get_drawings():
        r = drawing["rect"]
        if not (r.x0 >= x0 - 2 and r.x1 <= x1 + 2 and r.y0 >= y0 - 2 and r.y1 <= y1 + 2):
            continue
        for item in drawing["items"]:
            if item[0] != "re":
                continue
            rect = item[1]
            w, h = rect.x1 - rect.x0, rect.y1 - rect.y0
            if h <= THIN_RECT_MAX_THICKNESS:
                horizontal.append(rect)
            elif (
                w <= THIN_RECT_MAX_THICKNESS
                and h >= MIN_VERTICAL_RULE_HEIGHT
                and rect.x0 > x0 + 2
                and rect.x1 < x1 - 2
            ):
                vertical.append(rect)
    return horizontal, vertical


def _row_boundaries(horizontal_rects, bbox_top, bbox_bottom, table_width):
    """y-coordinates of rulings that span (close to) the full table width,
    always including the region's own top/bottom edge — a table with zero
    internal rulings is still one full-height row band, not "no table"."""
    horizontal_rects = sorted(horizontal_rects, key=lambda r: (r.y0 + r.y1) / 2)
    clusters = []
    for r in horizontal_rects:
        ymid = (r.y0 + r.y1) / 2
        if bbox_top - 1 <= ymid <= bbox_top + 1 or bbox_bottom - 1 <= ymid <= bbox_bottom + 1:
            continue  # the region's own outer border, not an internal divider
        if clusters and abs(ymid - clusters[-1][0]) <= ROW_BOUNDARY_Y_TOLERANCE:
            clusters[-1][1].append(r)
        else:
            clusters.append([ymid, [r]])

    boundaries = [bbox_top]
    for ymid, rects in clusters:
        spans = sorted((r.x0, r.x1) for r in rects)
        union, cur_start, cur_end = 0.0, spans[0][0], spans[0][1]
        for start, end in spans[1:]:
            if start <= cur_end + 0.5:
                cur_end = max(cur_end, end)
            else:
                union += cur_end - cur_start
                cur_start, cur_end = start, end
        union += cur_end - cur_start
        if union / table_width >= MIN_ROW_RULE_WIDTH_FRACTION:
            boundaries.append(ymid)
    boundaries.append(bbox_bottom)
    return boundaries


def _column_splits(vertical_rects, top, bottom):
    """x-coordinates of vertical dividers covering most of one row band's
    height — a row with none of these is a genuine single-column span."""
    row_height = bottom - top
    xs = [
        (r.x0 + r.x1) / 2
        for r in vertical_rects
        if min(r.y1, bottom) - max(r.y0, top) >= MIN_COLUMN_RULE_OVERLAP_FRACTION * row_height
    ]
    return sorted(xs)


def _render_cell(entries):
    """entries: list of (y, x, text) for one cell. Checkbox/widget glyphs
    can make PyMuPDF report slightly different y-coordinates for text that
    is visually on the same line, so lines are grouped by y-proximity
    (not exact y) before sorting left-to-right within each group."""
    entries = sorted(entries, key=lambda e: e[0])
    lines = []
    for y, x, text in entries:
        if lines and abs(y - lines[-1][0]) <= LINE_GROUP_Y_TOLERANCE:
            lines[-1][1].append((x, text))
            lines[-1][0] = (lines[-1][0] + y) / 2
        else:
            lines.append([y, [(x, text)]])
    return "\n".join(" ".join(t for _, t in sorted(items)) for _, items in lines)


def _reconstruct_from_rulings(page, bbox):
    """Rebuild a table's rows/columns from its ruling rectangles and text
    positions. Returns None if `bbox` has no ruling rectangles at all, so
    the caller can fall back to Table.extract()."""
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    horizontal_rects, vertical_rects = _thin_rects_in_bbox(page, bbox)
    if not horizontal_rects and not vertical_rects:
        return None

    boundaries = _row_boundaries(horizontal_rects, y0, y1, width)
    row_bands = list(zip(boundaries, boundaries[1:]))

    cells = [{} for _ in row_bands]
    text_dict = page.get_text("dict", clip=pymupdf.Rect(bbox))
    for block in text_dict["blocks"]:
        for line in block.get("lines", []):
            lx0, ly0, lx1, ly1 = line["bbox"]
            text = "".join(span["text"] for span in line["spans"]).strip()
            if not text:
                continue
            ymid = (ly0 + ly1) / 2
            row_idx = next(
                (i for i, (top, bottom) in enumerate(row_bands) if top - 1 <= ymid <= bottom + 1),
                None,
            )
            if row_idx is None:
                continue
            top, bottom = row_bands[row_idx]
            splits = _column_splits(vertical_rects, top, bottom)
            col_idx = bisect.bisect_right(splits, (lx0 + lx1) / 2)
            cells[row_idx].setdefault(col_idx, []).append((ly0, lx0, text))

    num_cols = max((max(row.keys(), default=0) for row in cells), default=0) + 1
    rows = [[_render_cell(row.get(c, [])) for c in range(num_cols)] for row in cells]

    # A row band with no text at all usually means one logical table row's
    # ruling got split across a page boundary and its text stayed on the
    # other page — drop it rather than emit an all-blank row.
    return [row for row in rows if any(cell.strip() for cell in row)]


def _is_meaningful(rows) -> bool:
    """Reject degenerate reconstructions (a single row and single column
    conveys no structure a plain paragraph didn't already have)."""
    if not rows:
        return False
    return len(rows) >= 2 or len(rows[0]) >= 2


def _find_tables_on_page(page):
    """PyMuPDF's own rule-based table finder, filtered to plausible tables."""
    tables = []
    for table in page.find_tables(strategy="lines_strict").tables:
        if table.row_count >= MIN_TABLE_ROWS and table.col_count >= MIN_TABLE_COLS:
            tables.append(table)
    return tables


TEXTUAL_CLASSES = {"text", "list-item"}
MIN_TEXTUAL_OVERLAP = 0.3


def _overlaps_real_text(bbox, page_boxes) -> bool:
    """Whether `bbox` meaningfully contains a page_box the layout model
    classified as genuine textual content ("text"/"list-item").

    find_tables() (rule-based, looks only for ruling lines) has no
    understanding of *content* — a decorative cover page's background
    color blocks, section-header titles, or footer graphics can easily
    look like a table grid to it even though there's no real table there
    at all. Requiring the candidate to actually contain some text the
    layout model recognized as prose is a much more reliable signal than
    trying to rule out "too much picture" directly — a page can be mostly
    non-picture (headers, footers) and still have no real table on it.

    If no page_boxes are available at all (no classification data to
    compare against), there's nothing to rule this out with, so
    find_tables() is trusted as-is.
    """
    if not page_boxes:
        return True
    for box in page_boxes:
        if box.get("class") not in TEXTUAL_CLASSES:
            continue
        if _overlap_fraction(tuple(box["bbox"]), bbox) >= MIN_TEXTUAL_OVERLAP:
            return True
    return False


def extract_tables(pdf_path: str, pages_boxes: list) -> list:
    pages_out = []
    with pymupdf.open(pdf_path) as doc:
        for page, page_boxes in zip(doc, pages_boxes):
            ml_table_bboxes = [tuple(b["bbox"]) for b in page_boxes if b.get("class") == "table"]
            rule_tables = _find_tables_on_page(page)

            candidates = list(ml_table_bboxes)
            for table in rule_tables:
                bbox = tuple(table.bbox)
                if any(_overlap_fraction(bbox, c) >= CANDIDATE_OVERLAP_THRESHOLD for c in ml_table_bboxes):
                    continue
                if not _overlaps_real_text(bbox, page_boxes):
                    continue
                candidates.append(bbox)

            tables_out = []
            for bbox in candidates:
                rows = _reconstruct_from_rulings(page, bbox)
                if not rows or not _is_meaningful(rows):
                    fallback_table = next(
                        (t for t in rule_tables if _overlap_fraction(tuple(t.bbox), bbox) >= CANDIDATE_OVERLAP_THRESHOLD),
                        None,
                    )
                    rows = fallback_table.extract() if fallback_table is not None else None
                if rows and _is_meaningful(rows):
                    tables_out.append({"bbox": list(bbox), "rows": rows})
            pages_out.append(tables_out)
    return pages_out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    pages_boxes_arg = json.loads(sys.stdin.read())
    json.dump(extract_tables(sys.argv[1], pages_boxes_arg), sys.stdout)
