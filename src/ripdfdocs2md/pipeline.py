"""Glue code: pick the right reader for a file, then run the cleanup pass.

This is the one place that knows about file extensions, so pdf_reader.py
and docx_reader.py stay focused on just their own format.
"""

from pathlib import Path

from . import docx_reader, pdf_reader
from .cleanup import clean_pages
from .letter_spacing import fix_letter_spacing

SUPPORTED_SUFFIXES = {".pdf", ".docx"}


class UnsupportedFileError(Exception):
    """Raised when a file can't be converted (wrong/unsupported format)."""


def convert_file(input_path: Path, assets_dir: Path | None = None) -> str:
    """Convert a single PDF or DOCX file to a cleaned Markdown string.

    `assets_dir`, if given, is where embedded images get written (see
    pdf_reader.convert_pages / docx_reader.convert for the exact naming
    and linking scheme); pass None to skip image export entirely.
    """
    suffix = input_path.suffix.lower()

    if suffix == ".pdf":
        pages = pdf_reader.convert_pages(input_path, assets_dir)
    elif suffix == ".docx":
        pages = [docx_reader.convert(input_path, assets_dir)]
    elif suffix == ".doc":
        raise UnsupportedFileError(
            "old binary .doc format is not supported (mammoth only reads "
            ".docx). Open it in Word or LibreOffice and use 'Save As' -> "
            ".docx, then convert again."
        )
    else:
        raise UnsupportedFileError(
            f"unsupported file type '{suffix}'. "
            f"Supported types: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )

    return fix_letter_spacing(clean_pages(pages))
