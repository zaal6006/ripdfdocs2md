"""Repair headings split into multiple Markdown bold spans with spurious
spaces at the split points.

pymupdf4llm's ML layout engine sometimes renders a heading's distinctive
display font as several separate **bold** spans instead of one continuous
run, with a spurious space inserted at each split — e.g.
"**THE DESJARDINS CEN** **TRE FOR ADV** **ANCED TRA** **INING**" instead
of "**THE DESJARDINS CENTRE FOR ADVANCED TRAINING**".

The spurious spaces don't reliably line up with the span boundaries
themselves (a run like "RESEARCH L" / "AND S" / "CAPE" needs "L", "AND",
"S", and "CAPE" all rejoined into "LANDSCAPE" — spanning across a
fragment's own internal space, not just the gaps between fragments), so
rather than deciding which individual gaps are wrong, we treat the whole
run of bold fragments as one blob and let word-frequency segmentation
(see word_segmentation.py) rebuild it from scratch — the same approach
already used for letter-spaced ALL-CAPS titles in letter_spacing.py.

Scoped to headings only: they're short, and Markdown bold there is purely
stylistic — unlike body text, a heading essentially never mixes in an
email, URL, or number that word segmentation could mangle (and on the
rare occasion one does, the alpha-only check below skips it). A heading
that was already fine (e.g. two separate bold clauses on one line) just
gets its words correctly re-derived and re-wrapped in one bold span — a
minor, harmless style normalization rather than a corruption.
"""

import re

from .word_segmentation import best_split, restore_case

_HEADING_RUN_RE = re.compile(r"^(?P<prefix>#{1,6}\s+)(?P<run>(?:\*\*[^*\n]+\*\*[ \t]*){2,})(?P<trail>.*)$")
_FRAGMENT_RE = re.compile(r"\*\*(.*?)\*\*")
_TAG_RE = re.compile(r"</?u>")


def _fix_line(line: str) -> str:
    match = _HEADING_RUN_RE.match(line)
    if not match:
        return line

    fragments = _FRAGMENT_RE.findall(match.group("run"))
    plain = " ".join(_TAG_RE.sub("", f) for f in fragments)
    blob = re.sub(r"\s+", "", plain)
    if not blob.isalpha():
        return line  # a number, punctuation, or email in the heading: too risky to reflow

    words = restore_case(blob, best_split(blob.lower()))
    return f"{match.group('prefix')}**{' '.join(words)}**{match.group('trail')}"


def fix_heading_fragments(text: str) -> str:
    """Repair fragmented headings line by line."""
    return "\n".join(_fix_line(line) for line in text.split("\n"))
