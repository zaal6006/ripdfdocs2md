"""Read a DOCX file and return its content as Markdown text.

Uses mammoth to convert DOCX to clean HTML (preserving headings, bold,
italic, and lists), then markdownify to turn that HTML into Markdown.
"""

from pathlib import Path

import mammoth
from markdownify import markdownify as html_to_markdown


def convert(docx_path: Path) -> str:
    """Convert a single DOCX file to a Markdown string."""
    with open(docx_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file)

    return html_to_markdown(result.value, heading_style="ATX", bullets="-")
