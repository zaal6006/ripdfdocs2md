"""Read a PDF file and return its content as Markdown text.

Uses pymupdf4llm, which inspects font sizes/styles to guess headings,
lists, and tables, and produces Markdown suited for feeding into an LLM.
"""

import contextlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pymupdf4llm

from .borderless_tables import convert_borderless_tables
from .heading_fragments import fix_heading_fragments
from .image_export import apply_renames, dedupe_directory
from .pdf_tables import inject_tables_into_page_text
from .strikethrough_fix import remove_spurious_strikethrough


class WorkerError(RuntimeError):
    """Raised when an isolated worker subprocess (table/checkbox
    detection) fails, with the worker's actual error message instead of
    just a bare exit code."""


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

    with tempfile.TemporaryDirectory() as tmp_dir:
        # Vector-drawn checkboxes (a small square, optionally with an X
        # or checkmark inside) are invisible to text extraction — they're
        # not font glyphs. Burn their state in as real "[ ]"/"[x]" text in
        # a throwaway copy first, so everything below (headings, tables,
        # paragraphs) picks it up automatically; see
        # _pdf_checkbox_worker.py for why this has to happen before
        # pymupdf4llm ever sees the file, not after.
        annotated_path = str(Path(tmp_dir) / Path(pdf_abs).name)
        checkbox_count = _annotate_checkboxes(pdf_abs, annotated_path)
        source_path = annotated_path if checkbox_count else pdf_abs

        if assets_dir is None:
            chunks = pymupdf4llm.to_markdown(source_path, page_chunks=True)
        else:
            # pymupdf4llm embeds image links relative to the process's
            # current directory, no matter what form image_path is given
            # in — so we point CWD at the output folder for the duration
            # of this call, and pass just the bare assets-folder name, to
            # get a link that's correctly relative to where the .md file
            # will live.
            with _chdir(assets_dir.parent):
                chunks = pymupdf4llm.to_markdown(
                    source_path, page_chunks=True, write_images=True, image_path=assets_dir.name
                )

        pages_boxes = [chunk.get("page_boxes") or [] for chunk in chunks]
        pages_tables = _extract_tables(source_path, pages_boxes)

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


def _run_worker(args: list, worker_name: str, **kwargs) -> str:
    """Run a worker subprocess and return its stdout. subprocess's own
    CalledProcessError message is just the command line and exit code —
    genuinely unhelpful for a corrupt/unusual PDF, where the worker's own
    stderr (a Python traceback) has the real reason. This surfaces that
    instead, so "ERROR: ..." in the CLI actually means something."""
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", **kwargs)
    if result.returncode != 0:
        last_line = next(
            (line for line in reversed(result.stderr.splitlines()) if line.strip()),
            "(no error output)",
        )
        raise WorkerError(f"{worker_name} failed: {last_line}")
    return result.stdout


def _annotate_checkboxes(pdf_path: str, output_path: str) -> int:
    """Run the checkbox-detection worker in its own process (see
    _pdf_checkbox_worker.py for why) and return how many checkboxes were
    found and burned into the copy at `output_path`."""
    stdout = _run_worker(
        [sys.executable, "-m", "ripdfdocs2md._pdf_checkbox_worker", pdf_path, output_path],
        "checkbox detection",
    )
    return int(stdout.strip())


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
    stdout = _run_worker(
        [sys.executable, "-m", "ripdfdocs2md._pdf_table_worker", str(pdf_path)],
        "table detection",
        input=json.dumps(pages_boxes),
    )
    return json.loads(stdout)
