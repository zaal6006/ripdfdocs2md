"""Detect and convert borderless, whitespace-aligned tables.

Some PDF tables have no vector-drawn borders at all (common in plain
reports, whitespace-aligned column layouts). Nothing in pdf_tables.py or
_pdf_table_worker.py can find these — both rely on ruling rectangles.
This is a text-only fallback: look at each blank-line-separated block of
already-extracted Markdown and, if it looks confidently tabular
(consistent whitespace-separated column count, numeric/short-token-heavy
content rather than prose), convert it to a Markdown table.

The column-splitting and scoring heuristic is adapted from the
whitespace-table detector in the open-source pdfmd project
(https://github.com/M1ck4/pdfmd, MIT licensed) — reused here because it
was already a well-considered solution to exactly this problem, tuned
to avoid misfiring on ordinary prose.
"""

import re

_CELL_SPLIT_CONSERVATIVE = re.compile(r"[ \t]{3,}")
_CELL_SPLIT_RELAXED = re.compile(r"[ \t]{2,}")
_SENTENCE_END_RE = re.compile(r"[.!?…]+$")
_LIST_MARKER_RE = re.compile(r"^(\d+|[A-Za-z])[.)]\s+")

MIN_ROWS = 2
MIN_COLS = 2
MIN_DENSITY = 0.25
MIN_SCORE = 1.0
MIN_COLUMN_COUNT_AGREEMENT = 0.6


def _split_cells(line: str) -> list:
    s = line.rstrip()
    if not s:
        return [""]
    cells = _CELL_SPLIT_CONSERVATIVE.split(s)
    if len(cells) >= 2:
        return cells
    return _CELL_SPLIT_RELAXED.split(s)


def _is_short_token(text: str) -> bool:
    s = text.strip()
    if not s or len(s) > 24 or " " in s:
        return False
    core = s.strip("()[]{}%$€£+-")
    if not core:
        return False
    return core.isdigit() or core.replace(".", "", 1).isdigit() or core.isalnum()


def _is_numeric(text: str) -> bool:
    s = text.strip().replace(",", "")
    if not s:
        return False
    core = s.replace(".", "", 1).replace("%", "", 1)
    if core.isdigit():
        return True
    return core.startswith("-") and core[1:].replace(".", "", 1).isdigit()


def _is_sentence(text: str) -> bool:
    s = text.strip()
    words = s.split()
    return len(words) >= 5 and bool(_SENTENCE_END_RE.search(s))


def _is_list_like(line: str) -> bool:
    s = line.lstrip()
    if not s:
        return False
    if s[0] in "-•◦*" and (len(s) == 1 or s[1].isspace()):
        return True
    return bool(_LIST_MARKER_RE.match(s))


def _most_common_count(values: list):
    counts = {}
    for v in values:
        counts[v] = counts.get(v, 0) + 1
    best = max(counts, key=counts.get)
    return best, counts[best]


def _score_grid(grid: list) -> float:
    """Higher is more table-like. Rewards numeric/short-token-heavy,
    dense, rectangular grids; penalizes prose (long sentence-like cells)."""
    n_rows = len(grid)
    n_cols = max((len(row) for row in grid), default=0)

    non_empty = short_tokens = numeric = sentences = 0
    lengths = []
    for row in grid:
        for cell in row:
            s = cell.strip()
            if not s:
                continue
            non_empty += 1
            lengths.append(len(s))
            if _is_short_token(s):
                short_tokens += 1
            if _is_numeric(s):
                numeric += 1
            if _is_sentence(s):
                sentences += 1

    total_cells = n_rows * n_cols
    density = non_empty / total_cells if total_cells else 0.0
    avg_len = sum(lengths) / len(lengths) if lengths else 0.0

    if density < MIN_DENSITY:
        return -999.0

    score = 1.0 * n_rows + 0.8 * n_cols
    if non_empty:
        score += 3.0 * (short_tokens / non_empty)
        score += 2.0 * (numeric / non_empty)
        sentence_ratio = sentences / non_empty
        if sentence_ratio > 0.8:
            score -= 4.0 * sentence_ratio
        elif sentence_ratio > 0.4:
            score -= 2.0 * sentence_ratio
    if avg_len > 120:
        score -= 5.0
    if n_rows >= 4 and n_cols >= 3:
        score += 2.0
    if len({len(row) for row in grid}) == 1:
        score += 1.5
    if density >= 0.6:
        score += 1.0

    return score


def _detect_grid(lines: list):
    """Try to read non-blank `lines` from one block as a whitespace
    -separated table. Returns a rectangular grid, or None."""
    if len(lines) < MIN_ROWS:
        return None
    if sum(1 for l in lines if _is_list_like(l)) >= max(2, int(0.8 * len(lines))):
        return None  # a bullet/numbered list, not a table

    split_lines = [_split_cells(l) for l in lines]
    is_row = [len(cells) >= MIN_COLS for cells in split_lines]
    if sum(is_row) < MIN_ROWS:
        return None

    row_counts = [len(cells) for cells, ok in zip(split_lines, is_row) if ok]
    target_cols, freq = _most_common_count(row_counts)
    if target_cols < MIN_COLS or freq < max(2, int(MIN_COLUMN_COUNT_AGREEMENT * len(row_counts))):
        return None

    grid = []
    for cells in split_lines:
        if len(cells) < target_cols:
            cells = cells + [""] * (target_cols - len(cells))
        elif len(cells) > target_cols:
            head = cells[: target_cols - 1]
            tail = " ".join(cells[target_cols - 1 :]).strip()
            cells = head + [tail]
        cleaned = [c.strip() for c in cells]
        if any(cleaned):
            grid.append(cleaned)

    return grid if len(grid) >= MIN_ROWS else None


def _clean_cell(text: str) -> str:
    for ch in ("\\", "`", "*", "_", "|"):
        text = text.replace(ch, "\\" + ch)
    return text


def _grid_to_markdown(grid: list) -> str:
    n_cols = max(len(row) for row in grid)
    rows = [row + [""] * (n_cols - len(row)) for row in grid]
    header, *body = rows
    lines = [
        "| " + " | ".join(_clean_cell(c) for c in header) + " |",
        "|" + "|".join(["---"] * n_cols) + "|",
    ]
    lines.extend("| " + " | ".join(_clean_cell(c) for c in row) + " |" for row in body)
    return "\n".join(lines)


def convert_borderless_tables(text: str) -> str:
    """Scan blank-line-separated blocks of `text` for whitespace-aligned
    tables with no Markdown table syntax already present, and convert any
    that score confidently as tabular into Markdown tables. Blocks that
    aren't confidently tabular (plain prose, lists, headings) are left
    untouched."""
    blocks = text.split("\n\n")
    out_blocks = []
    for block in blocks:
        stripped = block.lstrip()
        lines = [line for line in block.split("\n") if line.strip()]

        if stripped.startswith(("|", "#")) or len(lines) < MIN_ROWS:
            out_blocks.append(block)
            continue

        grid = _detect_grid(lines)
        if grid is None or _score_grid(grid) < MIN_SCORE:
            out_blocks.append(block)
            continue

        out_blocks.append(_grid_to_markdown(grid))

    return "\n\n".join(out_blocks)
