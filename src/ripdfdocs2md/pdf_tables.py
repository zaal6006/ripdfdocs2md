"""Fix tables that pymupdf4llm's layout model misclassifies as plain text.

pymupdf4llm (as of 1.28) uses an ML document-layout model by default, which
is generally better than the old rule-based extractor at detecting headings
and reading order — but it sometimes misclassifies a bordered, form-style
table (checkboxes, merged cells) as a generic "text" block, flattening the
whole thing into one run-on paragraph.

PyMuPDF's own `page.find_tables()` (rule-based, looks for ruling lines)
reliably finds these tables even when the layout model misses them — but
only in a process that never imported pymupdf4llm (its layout mode
monkey-patches table detection process-wide). See _pdf_table_worker.py,
which does that extraction in a separate process; this module just takes
its plain {"bbox": ..., "rows": ...} results and splices Markdown tables
into the layout model's output.

The splice point relies on pymupdf4llm's `page_chunks=True` output
including a `page_boxes` list per page: each entry has a `bbox` (the
region's location on the page) and a `pos` = (start, end) character offset
into that page's `text` string. That gives us an exact, safe splice point
instead of having to guess one from the Markdown text itself.
"""

import re

OVERLAP_THRESHOLD = 0.5


def _clean_cell(value) -> str:
    text = (value or "").strip()
    text = re.sub(r"\s*\n\s*", "<br>", text)
    return text.replace("|", "\\|")


def _rows_to_markdown(rows: list) -> str:
    """Build a Markdown pipe-table from extracted table rows."""
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    cleaned = [[_clean_cell(cell) for cell in row] + [""] * (width - len(row)) for row in rows]

    header, *body = cleaned
    lines = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join(["---"] * width) + "|",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in body)
    return "\n".join(lines) + "\n\n"


def _overlap_fraction(inner: tuple, outer: tuple) -> float:
    """Fraction of `inner`'s area that falls inside `outer`."""
    ix0, iy0 = max(inner[0], outer[0]), max(inner[1], outer[1])
    ix1, iy1 = min(inner[2], outer[2]), min(inner[3], outer[3])
    intersection = max(0.0, ix1 - ix0) * max(0.0, iy1 - iy0)
    inner_area = max(1e-6, (inner[2] - inner[0]) * (inner[3] - inner[1]))
    return intersection / inner_area


def inject_tables_into_page_text(text: str, page_boxes, tables: list) -> str:
    """Replace any layout-model block spanning a real table's area with a
    proper Markdown table built from `tables` (pre-extracted elsewhere —
    see _pdf_table_worker.py).

    `page_boxes` is the per-page list pymupdf4llm returns under the
    "page_boxes" key (only present when its ML layout model is active). If
    it's missing, we assume the caller's Markdown already handles tables
    itself and leave `text` untouched.
    """
    if not page_boxes or not tables:
        return text

    replacements = []  # list of (start, end, markdown)
    for table in tables:
        table_bbox = tuple(table["bbox"])
        matched = [b for b in page_boxes if _overlap_fraction(b["bbox"], table_bbox) >= OVERLAP_THRESHOLD]
        if not matched:
            continue  # layout model produced no block here; leave text alone
        start = min(b["pos"][0] for b in matched)
        end = max(b["pos"][1] for b in matched)
        replacements.append((start, end, _rows_to_markdown(table["rows"])))

    # Apply from the end of the string backward so earlier offsets stay valid.
    for start, end, markdown in sorted(replacements, key=lambda r: r[0], reverse=True):
        text = text[:start] + markdown + text[end:]

    return text
