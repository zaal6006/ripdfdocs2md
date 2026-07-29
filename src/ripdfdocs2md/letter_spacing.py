"""Fix PDF titles/headings extracted with manual character-spacing.

Some documents style their titles with letter-spacing/tracking
(e.g. "R E P O R T A N D A N A LY S I S" instead of "REPORT AND
ANALYSIS"). The PDF text layer preserves that as a literal space between
every character, and — unlike real word gaps — there is no reliable width
difference left in the extracted text to tell letter-gaps from
word-gaps apart. So instead of guessing from spacing, we detect lines
that are "suspiciously letter-by-letter", squash them back into one
blob, and use word-frequency-based segmentation (see word_segmentation.py)
to split the blob back into real words.
"""

import re

from .word_segmentation import best_split, restore_case

_MD_WRAP_RE = re.compile(
    r"^(?P<prefix>(?:#{1,6}\s+)?(?:\*\*|\*|__|_)?)"
    r"(?P<content>.*?)"
    r"(?P<suffix>(?:\*\*|\*|__|_)?)(?P<trail>\s*)$"
)

_MIN_TOKENS = 4
_SHORT_TOKEN_FRACTION = 0.7
_MAX_AVG_TOKEN_LEN = 1.6


def _is_letter_spaced(tokens: list[str]) -> bool:
    if len(tokens) < _MIN_TOKENS or not all(tok.isalpha() for tok in tokens):
        return False
    short = sum(1 for tok in tokens if len(tok) <= 2)
    avg_len = sum(len(tok) for tok in tokens) / len(tokens)
    return short / len(tokens) >= _SHORT_TOKEN_FRACTION and avg_len <= _MAX_AVG_TOKEN_LEN


def _fix_line(line: str) -> str:
    match = _MD_WRAP_RE.match(line)
    prefix, content, suffix, trail = match.group("prefix", "content", "suffix", "trail")

    tokens = [t for t in content.split(" ") if t]
    if not _is_letter_spaced(tokens):
        return line

    blob = "".join(tokens)
    words = restore_case(blob, best_split(blob.lower()))
    return f"{prefix}{' '.join(words)}{suffix}{trail}"


def fix_letter_spacing(text: str) -> str:
    """Collapse letter-spaced lines in `text` back into normal words."""
    return "\n".join(_fix_line(line) for line in text.split("\n"))
