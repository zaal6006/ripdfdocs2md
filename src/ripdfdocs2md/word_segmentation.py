"""Shared word-frequency-based segmentation for repairing fragmented text.

Used by both letter_spacing.py (per-character spaced-out titles) and
heading_fragments.py (headings split into multiple Markdown-formatting
spans with spurious spaces). Both problems reduce to the same operation:
take a blob of characters with unreliable/missing word boundaries and use
word-frequency dictionaries to reconstruct real words.

MUHC documents are bilingual (English/French Quebec), and the two
languages need different word-frequency dictionaries to segment
correctly — an English dictionary mangles French text into garbage
(e.g. "etablissementdesante" -> "et ablis semen tdes ante") and vice
versa. Rather than pulling in a separate language-detection library, we
just run both dictionaries and keep whichever produces the tighter fit
(fewer, longer words) — the wrong-language split reliably fragments into
more, shorter pieces.
"""

import wordninja_enhanced as wordninja

EN_MODEL = wordninja.LanguageModel("en")
FR_MODEL = wordninja.LanguageModel("fr")


def split_score(words: list[str]) -> tuple:
    """Lower is better: fewer words, and (as a tie-breaker) longer average
    word length — a wrong-language dictionary tends to fragment text into
    more, shorter pieces than the right one."""
    avg_len = sum(len(w) for w in words) / len(words)
    return (len(words), -avg_len)


def best_split(blob: str) -> list[str]:
    """Segment `blob` (already lowercased) with both the English and
    French dictionaries and keep whichever result fits better, without
    needing a dedicated language-detection step."""
    en_words = EN_MODEL.split(blob)
    fr_words = FR_MODEL.split(blob)
    return en_words if split_score(en_words) <= split_score(fr_words) else fr_words


def restore_case(blob: str, words: list[str]) -> list[str]:
    if blob.isupper():
        return [w.upper() for w in words]
    if blob.islower():
        return [w.lower() for w in words]
    return [w.capitalize() for w in words]
