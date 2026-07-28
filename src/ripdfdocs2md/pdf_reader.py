"""Read a PDF file and return its content as Markdown text.

Uses pymupdf4llm, which inspects font sizes/styles to guess headings,
lists, and tables, and produces Markdown suited for feeding into an LLM.
"""

from pathlib import Path

import pymupdf4llm


def convert(pdf_path: Path) -> str:
    """Convert a single PDF file to a Markdown string."""
    return pymupdf4llm.to_markdown(str(pdf_path))


def convert_pages(pdf_path: Path) -> list[str]:
    """Convert a PDF to a list of per-page Markdown strings.

    Used by the cleanup step, which needs page boundaries to detect
    repeating headers/footers and to rejoin paragraphs split across pages.
    """
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    return [chunk["text"] for chunk in chunks]
