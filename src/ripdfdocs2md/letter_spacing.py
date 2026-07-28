"""Fix PDF titles/headings extracted with manual character-spacing.

Some documents style their titles with letter-spacing/tracking
(e.g. "R E P O R T A N D A N A LY S I S" instead of "REPORT AND
ANALYSIS"). The PDF text layer preserves that as a literal space between
every character, and — unlike real word gaps — there is no reliable width
difference left in the extracted text to tell letter-gaps from
word-gaps apart. So instead of guessing from spacing, we detect lines
that are "suspiciously letter-by-letter", squash them back into one
blob, and use word-frequency-based segmentation (wordninja-enhanced) to
split the blob back into real words.

MUHC documents are bilingual (English/French Quebec), and the two
languages need different word-frequency dictionaries to segment
correctly — an English dictionary mangles French text into garbage
(e.g. "etablissementdesante" -> "et ablis semen tdes ante") and vice
versa. Rather than pulling in a separate language-detection library, we
just run both dictionaries and keep whichever produces the tighter fit
(fewer, longer words) — the wrong-language split reliably fragments
into more, shorter pieces.
"""

import re

import wordninja_enhanced as wordninja

_EN_MODEL = wordninja.LanguageModel("en")
_FR_MODEL = wordninja.LanguageModel("fr")

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


def _split_score(words: list[str]) -> tuple:
    """Lower is better: fewer words, and (as a tie-breaker) longer average
    word length — a wrong-language dictionary tends to fragment text into
    more, shorter pieces than the right one."""
    avg_len = sum(len(w) for w in words) / len(words)
    return (len(words), -avg_len)


def _best_split(blob: str) -> list[str]:
    """Segment `blob` with both the English and French dictionaries and
    keep whichever result fits better, without needing a dedicated
    language-detection step."""
    en_words = _EN_MODEL.split(blob)
    fr_words = _FR_MODEL.split(blob)
    return en_words if _split_score(en_words) <= _split_score(fr_words) else fr_words


def _restore_case(blob: str, words: list[str]) -> list[str]:
    if blob.isupper():
        return [w.upper() for w in words]
    if blob.islower():
        return [w.lower() for w in words]
    return [w.capitalize() for w in words]


def _fix_line(line: str) -> str:
    match = _MD_WRAP_RE.match(line)
    prefix, content, suffix, trail = match.group("prefix", "content", "suffix", "trail")

    tokens = [t for t in content.split(" ") if t]
    if not _is_letter_spaced(tokens):
        return line

    blob = "".join(tokens)
    words = _restore_case(blob, _best_split(blob.lower()))
    return f"{prefix}{' '.join(words)}{suffix}{trail}"


def fix_letter_spacing(text: str) -> str:
    """Collapse letter-spaced lines in `text` back into normal words."""
    return "\n".join(_fix_line(line) for line in text.split("\n"))
