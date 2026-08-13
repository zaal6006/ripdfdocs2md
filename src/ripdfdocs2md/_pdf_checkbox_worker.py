"""Standalone worker: detect vector-drawn checkboxes and burn their
checked/unchecked state into the PDF as real text.

Checkboxes drawn as vector shapes (a small square outline, optionally
with a mark like an X or checkmark drawn inside it) are invisible to text
extraction entirely — PyMuPDF's text extraction only sees font glyphs,
and these are just line drawings, so they vanish without a trace today.

Rather than trying to splice a symbol into pymupdf4llm's already-generated
Markdown (which has no per-word position info to splice against), we
solve it one layer down: detect each checkbox's position and state here,
then insert real "[ ]" / "[x]" text at that exact spot in a throwaway
copy of the PDF, *before* pymupdf4llm ever sees it. Its own layout engine
then picks the inserted text up naturally, in the correct reading-order
position relative to the checkbox's label — no manual label-matching
needed, and it works whether the checkbox sits inside a table cell or
in ordinary paragraph text.

Runs in its own process for the same reason _pdf_table_worker.py does:
pymupdf4llm's ML layout mode monkey-patches PyMuPDF process-wide, and this
needs the original, unpatched vector-drawing behavior.

Detection: a checkbox is a small (~5-20pt), roughly square cluster of
line-drawing ("l") shapes tracing a closed rectangle. An empty box alone
means unchecked; a diagonal stroke inside it (an X, a checkmark, however
this particular PDF draws its mark) or any additional shape drawn inside
it means checked. We don't try to enumerate every possible checkmark
shape — "there's a border, and something extra inside it" is a reliable
enough signal on its own.
"""

import itertools
import sys

import pymupdf

MIN_BOX_SIZE = 5.0
MAX_BOX_SIZE = 20.0
MIN_ASPECT_RATIO = 0.6
MAX_ASPECT_RATIO = 1.6
CLUSTER_TOLERANCE = 2.0
MIN_BORDER_SPAN_FRACTION = 0.7
MIN_DIAGONAL_SPAN_FRACTION = 0.5
NEARBY_TEXT_MARGIN = 6.0
MAX_DARK_COLOR_VALUE = 0.4
MAX_COLOR_SATURATION = 0.15


def _rects_close(a, b, tol: float = CLUSTER_TOLERANCE) -> bool:
    return (
        abs(a.x0 - b.x0) <= tol
        and abs(a.y0 - b.y0) <= tol
        and abs(a.x1 - b.x1) <= tol
        and abs(a.y1 - b.y1) <= tol
    )


def _cluster_drawings(drawings: list) -> list:
    """Group drawings whose bboxes are (near-)identical — a checkbox's
    border and any mark drawn inside it share almost the same footprint."""
    clusters = []
    for d in drawings:
        rect = d["rect"]
        for cluster in clusters:
            if _rects_close(cluster["rect"], rect):
                cluster["drawings"].append(d)
                break
        else:
            clusters.append({"rect": rect, "drawings": [d]})
    return clusters


def _is_checkbox_shaped(rect) -> bool:
    w, h = rect.x1 - rect.x0, rect.y1 - rect.y0
    if not (MIN_BOX_SIZE <= w <= MAX_BOX_SIZE and MIN_BOX_SIZE <= h <= MAX_BOX_SIZE):
        return False
    if h == 0:
        return False
    ratio = w / h
    return MIN_ASPECT_RATIO <= ratio <= MAX_ASPECT_RATIO


def _item_points(item) -> list:
    """Endpoints of a plain line ("l") item, the only item type real
    checkbox borders/marks were observed to use for individual strokes
    (as opposed to a native rectangle, "re", handled separately)."""
    if item[0] == "l":
        return [item[1], item[2]]
    return []


def _has_border_outline(cluster) -> bool:
    """Whether some drawing in the cluster traces close to the cluster's
    own full bounding box — i.e. there's a box here, not just a stray
    mark that happened to be clustered with nothing around it. Handles
    both ways a border tends to get drawn: a native stroked/filled
    rectangle ("re", one item), or a hand-drawn outline built from
    several line segments (checked collectively)."""
    rect = cluster["rect"]
    w, h = rect.x1 - rect.x0, rect.y1 - rect.y0
    for d in cluster["drawings"]:
        for item in d["items"]:
            if item[0] == "re":
                r = item[1]
                if (r.x1 - r.x0) >= MIN_BORDER_SPAN_FRACTION * w and (
                    r.y1 - r.y0
                ) >= MIN_BORDER_SPAN_FRACTION * h:
                    return True

        points = [pt for item in d["items"] for pt in _item_points(item)]
        if len(points) < 4:
            continue
        xs, ys = [p.x for p in points], [p.y for p in points]
        if (max(xs) - min(xs)) >= MIN_BORDER_SPAN_FRACTION * w and (
            max(ys) - min(ys)
        ) >= MIN_BORDER_SPAN_FRACTION * h:
            return True
    return False


def _is_dark_neutral(rgb) -> bool:
    r, g, b = rgb
    return max(r, g, b) <= MAX_DARK_COLOR_VALUE and (max(r, g, b) - min(r, g, b)) <= MAX_COLOR_SATURATION


def _is_dark_colored(cluster) -> bool:
    """Whether every colored drawing in the cluster is black/dark-gray,
    rather than a vivid hue. Real form checkboxes are essentially always
    drawn in black or dark gray; a colorful icon or badge graphic (common
    in a branded, heavily-designed document) can otherwise coincidentally
    match the size/shape/nearby-text checks too."""
    for d in cluster["drawings"]:
        for key in ("fill", "color"):
            rgb = d.get(key)
            if rgb is not None and not _is_dark_neutral(rgb):
                return False
    return True


def _has_checked_mark(cluster) -> bool:
    """Whether the cluster has a genuine diagonal stroke (an X or
    checkmark's main strokes are never purely horizontal/vertical the way
    a box border's segments are) or more shapes than a single outline
    would need — either is taken as "checked"."""
    rect = cluster["rect"]
    w, h = rect.x1 - rect.x0, rect.y1 - rect.y0
    if w and h:
        for d in cluster["drawings"]:
            for item in d["items"]:
                points = _item_points(item)
                for p1, p2 in itertools.combinations(points, 2):
                    dx, dy = abs(p1.x - p2.x), abs(p1.y - p2.y)
                    if dx >= MIN_DIAGONAL_SPAN_FRACTION * w and dy >= MIN_DIAGONAL_SPAN_FRACTION * h:
                        return True
    return len(cluster["drawings"]) > 1


def _page_text_spans(page) -> list:
    """Return (bbox, is_bold) for every text span on the page, gathered
    once so each checkbox candidate can be checked against it cheaply."""
    spans = []
    text = page.get_text("dict")
    for block in text["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                is_bold = bool(span["flags"] & 2**4) or "bold" in span["font"].lower()
                spans.append((pymupdf.Rect(span["bbox"]), is_bold))
    return spans


def _has_plain_nearby_text(spans: list, rect) -> bool:
    """Whether some non-bold text sits immediately beside this checkbox,
    on the same line, close enough to plausibly be its label. A genuine
    checkbox+label pair sit right next to each other with essentially no
    gap (confirmed against real examples); a decorative graphic (an icon,
    a logo, an accent mark within a heading) can still have *some* text
    within a loose radius, but it's incidental — a stray word from
    nearby running text, not a deliberately adjacent label — so both a
    same-line check and a tight horizontal gap are required, not just
    "somewhere nearby"."""
    for span_rect, is_bold in spans:
        if is_bold:
            continue
        y_overlap = min(rect.y1, span_rect.y1) - max(rect.y0, span_rect.y0)
        if y_overlap <= 0:
            continue
        x_gap = max(span_rect.x0 - rect.x1, rect.x0 - span_rect.x1, 0.0)
        if x_gap <= NEARBY_TEXT_MARGIN:
            return True
    return False


def find_checkboxes(page) -> list:
    """Return a list of (rect, checked) for every checkbox-shaped cluster
    of vector drawings on `page` that also has a plain-text label nearby."""
    drawings = [d for d in page.get_drawings() if d["items"]]
    spans = _page_text_spans(page)

    checkboxes = []
    for cluster in _cluster_drawings(drawings):
        rect = cluster["rect"]
        if not _is_checkbox_shaped(rect):
            continue
        if not _has_border_outline(cluster):
            continue
        if not _is_dark_colored(cluster):
            continue
        if not _has_plain_nearby_text(spans, rect):
            continue
        checkboxes.append((rect, _has_checked_mark(cluster)))
    return checkboxes


def annotate_checkboxes(input_path: str, output_path: str) -> int:
    """Write a copy of the PDF at `input_path` to `output_path` with a
    "[ ]" or "[x]" burned in as real text over every detected checkbox.
    Returns the total number of checkboxes found."""
    doc = pymupdf.open(input_path)
    total = 0
    for page in doc:
        for rect, checked in find_checkboxes(page):
            label = "[x]" if checked else "[ ]"
            fontsize = max(6.0, min(rect.y1 - rect.y0, 11.0))
            page.insert_text(
                (rect.x0, rect.y1 - fontsize * 0.2), label, fontsize=fontsize, fontname="helv"
            )
            total += 1
    doc.save(output_path)
    doc.close()
    return total


if __name__ == "__main__":
    checkbox_count = annotate_checkboxes(sys.argv[1], sys.argv[2])
    print(checkbox_count)
