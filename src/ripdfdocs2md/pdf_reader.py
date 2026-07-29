"""Read a PDF file and return its content as Markdown text.

Uses pymupdf4llm, which inspects font sizes/styles to guess headings,
lists, and tables, and produces Markdown suited for feeding into an LLM.
"""

import json
import subprocess
import sys
from pathlib import Path

import pymupdf4llm

from .borderless_tables import convert_borderless_tables
from .pdf_tables import inject_tables_into_page_text


def convert(pdf_path: Path) -> str:
    """Convert a single PDF file to a Markdown string."""
    return pymupdf4llm.to_markdown(str(pdf_path))


def convert_pages(pdf_path: Path) -> list[str]:
    """Convert a PDF to a list of per-page Markdown strings.

    Used by the cleanup step, which needs page boundaries to detect
    repeating headers/footers and to rejoin paragraphs split across pages.
    """
    chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)
    pages_boxes = [chunk.get("page_boxes") or [] for chunk in chunks]
    pages_tables = _extract_tables(pdf_path, pages_boxes)

    pages = [
        inject_tables_into_page_text(chunk["text"], chunk.get("page_boxes"), tables)
        for chunk, tables in zip(chunks, pages_tables)
    ]
    # Ruling-based detection only finds tables with vector-drawn borders;
    # this catches whitespace-aligned tables that have none at all.
    return [convert_borderless_tables(page) for page in pages]


def _extract_tables(pdf_path: Path, pages_boxes: list) -> list:
    """Run the table-extraction worker in its own process (see
    _pdf_table_worker.py for why this can't be done in-process) and return
    its per-page table list. `pages_boxes` (the layout model's own block
    classifications) is passed in via stdin so the worker can use its
    "table"-classified regions as the primary source of where tables are."""
    result = subprocess.run(
        [sys.executable, "-m", "ripdfdocs2md._pdf_table_worker", str(pdf_path)],
        input=json.dumps(pages_boxes),
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return json.loads(result.stdout)
