"""Verify that every image link in a converted Markdown file points to a
real, valid image file — a quick automated check you can run instead of
(or before) opening the file in a Markdown viewer.
"""

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path

from .console import use_utf8_console

_IMAGE_LINK_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")

_EXTENSION_MAGIC = {
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
    ".gif": (b"GIF87a", b"GIF89a"),
    ".bmp": (b"BM",),
}


def _looks_like_a_real_image(path: Path) -> bool:
    """Best-effort validity check via magic bytes for common formats — if
    the extension is one we recognize, the file's actual header must
    match it, catching e.g. a truncated/corrupt "image.png" that isn't
    really PNG data. An unrecognized extension (rare — old Word docs
    occasionally embed vector formats like .emf/.wmf) falls back to a
    "non-empty file" check, since there's no simple signature for those."""
    header = path.read_bytes()[:12]
    if not header:
        return False

    ext = path.suffix.lower()
    if ext == ".webp":
        return header[:4] == b"RIFF" and header[8:12] == b"WEBP"

    magics = _EXTENSION_MAGIC.get(ext)
    if magics is not None:
        return any(header.startswith(magic) for magic in magics)

    return True


@dataclass
class VerifyResult:
    md_path: Path
    total_links: int = 0
    missing: list = field(default_factory=list)
    invalid: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.missing and not self.invalid


def verify_file(md_path: Path) -> VerifyResult:
    """Check every image link in `md_path` resolves to an existing, valid
    image file, relative to the Markdown file's own folder (matching how
    any standard Markdown viewer would resolve the same link).

    A "data:" URI (an image embedded inline as base64 — e.g. mammoth's
    default when image export is skipped) is self-contained rather than a
    file reference, so it's counted but never flagged as missing/invalid.
    """
    text = md_path.read_text(encoding="utf-8")
    links = _IMAGE_LINK_RE.findall(text)

    result = VerifyResult(md_path=md_path, total_links=len(links))
    for link in links:
        if link.startswith("data:"):
            continue
        resolved = md_path.parent / link
        if not resolved.is_file():
            result.missing.append(link)
        elif not _looks_like_a_real_image(resolved):
            result.invalid.append(link)
    return result


def _find_markdown_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(sorted(path.glob("*.md")))
        elif path.is_file():
            files.append(path)
        else:
            print(f"Warning: {path} does not exist, skipping.")
    return files


def main(argv: list[str] | None = None) -> int:
    use_utf8_console()

    parser = argparse.ArgumentParser(
        prog="ripdfdocs2md-verify",
        description="Check that every image link in a converted Markdown file "
        "points to a real, valid image file.",
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        type=Path,
        help="One or more .md files, or folders containing them.",
    )
    args = parser.parse_args(argv)

    md_files = _find_markdown_files(args.inputs)
    if not md_files:
        print("No .md files found.")
        return 1

    all_ok = True
    for md_path in md_files:
        result = verify_file(md_path)
        status = "OK" if result.ok else "PROBLEMS"
        print(f"{md_path}: {result.total_links} image link(s) - {status}")
        for link in result.missing:
            print(f"  MISSING: {link}")
        for link in result.invalid:
            print(f"  INVALID (not a recognizable image): {link}")
        if not result.ok:
            all_ok = False

    print()
    print("All images verified OK." if all_ok else "Some images are missing or invalid - see above.")
    return 0 if all_ok else 1
