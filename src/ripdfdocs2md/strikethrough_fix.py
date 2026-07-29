"""Strip spurious strikethrough markup from PDF extraction.

pymupdf4llm's ML layout engine occasionally misdetects a font's rendering
(observed on stylized headings and, less often, ordinary body text in
documents with a distinctive display font) as strikethrough formatting,
wrapping random word fragments in "~~...~~" — e.g. "The I~~nstitute~~"
instead of "The Institute". Across every real document we've checked,
every single instance of this has been spurious (genuine strikethrough is
essentially never used in the kind of institutional documents this tool
targets), so the safe, low-risk fix is to unwrap it entirely rather than
try to guess which instances (if any) are intentional.
"""

import re

_STRIKETHROUGH_RE = re.compile(r"~~(.*?)~~")


def remove_spurious_strikethrough(text: str) -> str:
    """Unwrap every ~~...~~ span, keeping the inner text."""
    return _STRIKETHROUGH_RE.sub(r"\1", text)
