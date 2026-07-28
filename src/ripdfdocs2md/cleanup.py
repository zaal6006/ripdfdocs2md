"""Post-processing cleanup for extracted Markdown.

Two independent problems, both caused by processing a document page by page:

1. Repeating headers/footers: running titles, page numbers, confidentiality
   notices, etc. that appear on (almost) every page and add noise for a
   downstream chatbot.
2. Paragraphs broken across a page boundary: pymupdf4llm already joins
   line-wraps *within* a page, but a sentence or hyphenated word that
   happens to land exactly at the end of one page and the start of the
   next is left split in two.
"""

import re
from collections import Counter

_DIGIT_RE = re.compile(r"\d+")
_SENTENCE_END_RE = re.compile(r"[.!?:;]\s*$")
_BLOCK_STARTER_RE = re.compile(r"^\s*(#{1,6}\s|[-*+]\s|\d+[.)]\s|\|)")


def _fingerprint(line: str) -> str:
    """Normalize a line so lines that differ only by a page number
    (e.g. "Page 1 of 2" vs "Page 2 of 2") are treated as the same line."""
    return _DIGIT_RE.sub("#", line.strip().lower())


def remove_repeating_boilerplate(
    page_texts: list[str], threshold: float = 0.6, zone: int = 2
) -> list[str]:
    """Strip lines that repeat, near-identically, in the header/footer zone
    of most pages.

    `zone` is how many leading/trailing non-blank lines of each page count
    as "header/footer zone" — content in the middle of a page is never
    touched, even if it happens to repeat (e.g. the same bullet point
    appearing on two different pages is left alone).

    `threshold` is the fraction of pages a line must appear in (in that
    zone) before it is considered boilerplate rather than coincidence.
    """
    num_pages = len(page_texts)
    if num_pages < 2:
        return page_texts

    pages_lines = [text.split("\n") for text in page_texts]

    # For each page, work out which line indexes fall in the header/footer
    # zone, and the set of fingerprints found there.
    zones: list[set[int]] = []
    fingerprints_per_page: list[set[str]] = []
    for lines in pages_lines:
        non_blank_idx = [i for i, l in enumerate(lines) if l.strip()]
        zone_idx = set(non_blank_idx[:zone]) | set(non_blank_idx[-zone:])
        zones.append(zone_idx)
        fingerprints_per_page.append({_fingerprint(lines[i]) for i in zone_idx})

    counts = Counter()
    for fps in fingerprints_per_page:
        for fp in fps:
            counts[fp] += 1

    removal = {fp for fp, c in counts.items() if fp and c / num_pages >= threshold}

    cleaned_pages = []
    for lines, zone_idx in zip(pages_lines, zones):
        cleaned = [
            line
            for i, line in enumerate(lines)
            if not (i in zone_idx and _fingerprint(line) in removal)
        ]
        cleaned_pages.append("\n".join(cleaned))

    return cleaned_pages


def _first_nonblank_index(lines: list[str]):
    for i, line in enumerate(lines):
        if line.strip():
            return i
    return None


def _last_nonblank_index(lines: list[str]):
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i
    return None


def join_pages(page_texts: list[str]) -> str:
    """Join per-page Markdown into one document, re-joining a paragraph (or
    hyphenated word) that was split exactly across a page boundary."""
    if not page_texts:
        return ""

    merged_lines = page_texts[0].split("\n")

    for next_text in page_texts[1:]:
        next_lines = next_text.split("\n")
        first_idx = _first_nonblank_index(next_lines)
        if first_idx is None:
            continue  # blank page, nothing to add

        last_idx = _last_nonblank_index(merged_lines)
        if last_idx is None:
            merged_lines = next_lines
            continue

        last_line = merged_lines[last_idx].strip()
        first_line = next_lines[first_idx].strip()

        continues = (
            not _SENTENCE_END_RE.search(last_line)
            and not _BLOCK_STARTER_RE.match(first_line)
            and first_line[:1].islower()
        )

        if continues:
            if last_line.endswith("-"):
                merged_lines[last_idx] = last_line[:-1] + first_line
            else:
                merged_lines[last_idx] = last_line + " " + first_line
            merged_lines = merged_lines[: last_idx + 1] + next_lines[first_idx + 1 :]
        else:
            merged_lines = merged_lines + ["", ""] + next_lines

    return "\n".join(merged_lines).strip() + "\n"


_MULTI_BLANK_RE = re.compile(r"\n{3,}")


def collapse_blank_lines(text: str) -> str:
    """Collapse 3+ consecutive newlines down to a single blank line.

    Stripping a header/footer line can leave a gap where it used to be;
    this keeps paragraph spacing consistent instead of leaving craters.
    """
    return _MULTI_BLANK_RE.sub("\n\n", text)


def clean_pages(page_texts: list[str], boilerplate_threshold: float = 0.6) -> str:
    """Full cleanup pipeline: strip repeating headers/footers, rejoin
    paragraphs split across page boundaries, and tidy up blank lines."""
    deduped = remove_repeating_boilerplate(page_texts, threshold=boilerplate_threshold)
    joined = join_pages(deduped)
    return collapse_blank_lines(joined)
