"""Read a PDF file and return its content as Markdown text.

Uses pymupdf4llm, which inspects font sizes/styles to guess headings,
lists, and tables, and produces Markdown suited for feeding into an LLM.
"""

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pymupdf4llm

from .borderless_tables import convert_borderless_tables
from .heading_fragments import fix_heading_fragments
from .image_export import apply_renames, dedupe_directory
from .pdf_tables import inject_tables_into_page_text
from .strikethrough_fix import remove_spurious_strikethrough


def convert(pdf_path: Path) -> str:
    """Convert a single PDF file to a Markdown string."""
    return pymupdf4llm.to_markdown(str(pdf_path))


def convert_pages(pdf_path: Path, assets_dir: Path | None = None) -> list[str]:
    """Convert a PDF to a list of per-page Markdown strings.

    Used by the cleanup step, which needs page boundaries to detect
    repeating headers/footers and to rejoin paragraphs split across pages.

    If `assets_dir` is given, embedded images are written there (named
    by pymupdf4llm, e.g. "report.pdf-0001-01.png") and linked into the
    Markdown as "<assets_dir.name>/<filename>" — relative to the folder
    the final .md file itself will live in (assets_dir's parent).
    Byte-identical images (e.g. a logo repeated on every page) are
    deduplicated down to a single shared file. If None, images are
    skipped entirely.
    """
    pdf_abs = str(Path(pdf_path).resolve())

    if assets_dir is None:
        chunks = pymupdf4llm.to_markdown(pdf_abs, page_chunks=True)
    else:
        # pymupdf4llm embeds image links relative to the process's
        # current directory, no matter what form image_path is given in
        # — so we point CWD at the output folder for the duration of
        # this call, and pass just the bare assets-folder name, to get a
        # link that's correctly relative to where the .md file will live.
        with _chdir(assets_dir.parent):
            chunks = pymupdf4llm.to_markdown(
                pdf_abs, page_chunks=True, write_images=True, image_path=assets_dir.name
            )

    pages_boxes = [chunk.get("page_boxes") or [] for chunk in chunks]
    pages_tables = _extract_tables(pdf_abs, pages_boxes)

    pages = [
        inject_tables_into_page_text(chunk["text"], chunk.get("page_boxes"), tables)
        for chunk, tables in zip(chunks, pages_tables)
    ]
    # Ruling-based detection only finds tables with vector-drawn borders;
    # this catches whitespace-aligned tables that have none at all.
    pages = [convert_borderless_tables(page) for page in pages]
    # pymupdf4llm's ML layout mode sometimes misdetects a font's rendering
    # as strikethrough on stylized headings; see strikethrough_fix.py.
    pages = [remove_spurious_strikethrough(page) for page in pages]
    # ...and sometimes splits a heading across multiple bold spans with a
    # spurious space at the split; see heading_fragments.py.
    pages = [fix_heading_fragments(page) for page in pages]

    if assets_dir is not None:
        renames = dedupe_directory(assets_dir)
        if renames:
            pages = [apply_renames(page, renames) for page in pages]
        _remove_dir_if_empty(assets_dir)

    return pages


def _remove_dir_if_empty(path: Path) -> None:
    if path.exists() and not any(path.iterdir()):
        path.rmdir()


@contextlib.contextmanager
def _chdir(path: Path):
    original = Path.cwd()
    path.mkdir(parents=True, exist_ok=True)
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(original)


def _extract_tables(pdf_path: str, pages_boxes: list) -> list:
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
