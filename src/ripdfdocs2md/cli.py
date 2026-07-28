"""Command-line interface for ripdfdocs2md.

Examples:
    ripdfdocs2md samples/some_file.pdf
    ripdfdocs2md samples/some_file.docx -o output
    ripdfdocs2md samples/                       # convert every PDF/DOCX in a folder
    ripdfdocs2md samples/ -o output
"""

import argparse
import sys
from pathlib import Path

from .pipeline import SUPPORTED_SUFFIXES, UnsupportedFileError, convert_file

KNOWN_UNSUPPORTED_SUFFIXES = {".doc"}


def _use_utf8_console() -> None:
    """Windows terminals often default to a legacy codepage (e.g. cp1252)
    that can't encode many filenames (accents, Cyrillic, etc.). Force
    UTF-8 output so an unusual filename can't crash the whole batch."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def _collect_input_files(paths: list[Path]) -> tuple[list[Path], int]:
    """Expand a mix of file paths and folder paths into a flat file list.

    Returns (files_to_convert, skipped_count) — skipped_count covers files
    recognized as unsupported (e.g. .doc) before conversion is even tried.
    """
    files: list[Path] = []
    skipped = 0
    for path in paths:
        if path.is_dir():
            for suffix in SUPPORTED_SUFFIXES:
                files.extend(sorted(path.glob(f"*{suffix}")))
            for suffix in KNOWN_UNSUPPORTED_SUFFIXES:
                for bad_file in sorted(path.glob(f"*{suffix}")):
                    print(f"Skipping {bad_file.name}: old .doc format not supported (see README).")
                    skipped += 1
        elif path.is_file():
            files.append(path)
        else:
            print(f"Warning: {path} does not exist, skipping.")
    return files, skipped


def _build_output_path(input_path: Path, output_dir: Path, used: set) -> Path:
    """Pick an output .md path for input_path, disambiguating same-stem
    files with different extensions (e.g. demo.pdf and demo.docx) so one
    never silently overwrites the other."""
    candidate = output_dir / (input_path.stem + ".md")
    if candidate not in used:
        return candidate
    suffix = input_path.suffix.lstrip(".")
    return output_dir / f"{input_path.stem}__{suffix}.md"


def main(argv: list[str] | None = None) -> int:
    _use_utf8_console()

    parser = argparse.ArgumentParser(
        prog="ripdfdocs2md",
        description="Convert PDF/DOCX files to Markdown, fully offline.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more PDF/DOCX files, or folders containing them.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Folder to write .md files into (default: output/).",
    )
    args = parser.parse_args(argv)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    files, skipped = _collect_input_files(args.inputs)
    if not files:
        print("No PDF/DOCX files found.")
        return 1

    converted = 0
    failed = 0
    used_output_paths: set = set()
    for input_path in files:
        out_path = _build_output_path(input_path, args.output_dir, used_output_paths)
        used_output_paths.add(out_path)

        print(f"Converting {input_path.name} -> {out_path}")
        try:
            markdown = convert_file(input_path)
        except UnsupportedFileError as exc:
            print(f"  SKIPPED: {exc}")
            skipped += 1
            continue
        except Exception as exc:  # noqa: BLE001 - keep batch going on a bad file
            print(f"  ERROR: {exc}")
            failed += 1
            continue

        out_path.write_text(markdown, encoding="utf-8")
        converted += 1

    print(f"\nDone: {converted} converted, {failed} failed, {skipped} skipped (unsupported format).")
    return 0 if failed == 0 and skipped == 0 else 1
