"""Command-line interface for ripdfdocs2md.

Examples:
    ripdfdocs2md samples/some_file.pdf
    ripdfdocs2md samples/some_file.docx -o output
    ripdfdocs2md samples/                       # convert every PDF/DOCX in a folder
    ripdfdocs2md samples/ -o output
    ripdfdocs2md samples/ --no-images           # skip extracting embedded images
"""

import argparse
import re
from pathlib import Path

from .console import use_utf8_console
from .pipeline import SUPPORTED_SUFFIXES, UnsupportedFileError, convert_file

KNOWN_UNSUPPORTED_SUFFIXES = {".doc"}
_WHITESPACE_RE = re.compile(r"\s+")


def _assets_dir_name(stem: str) -> str:
    """pymupdf4llm's image writer has a bug where it sanitizes spaces out
    of the filename it constructs but not out of the directory it actually
    creates, crashing with "no such file or directory" whenever the
    assets folder name contains one — so this is space-free even when the
    .md file's own name isn't."""
    return _WHITESPACE_RE.sub("_", stem) + "_assets"


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
    """Pick an output .md path for input_path, renaming with a numeric
    suffix (report.md, report_1.md, report_2.md, ...) if the name is
    already taken — e.g. two same-named files from different input
    folders, or demo.pdf and demo.docx both wanting "demo.md" — so one
    never silently overwrites the other."""
    candidate = output_dir / (input_path.stem + ".md")
    if candidate not in used:
        return candidate
    n = 1
    while True:
        candidate = output_dir / f"{input_path.stem}_{n}.md"
        if candidate not in used:
            return candidate
        n += 1


def main(argv: list[str] | None = None) -> int:
    use_utf8_console()

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
    parser.add_argument(
        "--no-images",
        action="store_true",
        help="Skip extracting embedded images (by default, images are saved into a "
        "<name>_assets/ folder next to each output file and linked from the Markdown).",
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

        assets_dir = None if args.no_images else out_path.with_name(_assets_dir_name(out_path.stem))

        print(f"Converting {input_path.name} -> {out_path}")
        try:
            markdown = convert_file(input_path, assets_dir)
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
