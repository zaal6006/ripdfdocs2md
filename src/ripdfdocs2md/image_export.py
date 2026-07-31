"""Save extracted images into a per-document assets folder next to the
Markdown output, deduplicating byte-identical images (e.g. a letterhead
logo repeated on every page) so they don't get one wasteful copy per
occurrence.

Used two different ways depending on the reader:
- docx_reader.py controls image writing directly (mammoth hands us each
  image's raw bytes via a callback), so it uses ImageSaver, which hashes
  and writes as it goes.
- pdf_reader.py doesn't get that callback — pymupdf4llm writes image
  files itself. So dedupe_directory() runs afterward: hash whatever was
  already written, delete byte-identical duplicates, and hand back a
  rename map for the caller to apply to the Markdown text it already has.
"""

import hashlib
from pathlib import Path


class ImageSaver:
    """Writes image bytes under `assets_dir` and returns a Markdown-ready
    link (relative to assets_dir's parent — the folder the .md file
    itself will live in). An image whose bytes exactly match one already
    saved reuses that file instead of writing a duplicate."""

    def __init__(self, assets_dir: Path):
        self.assets_dir = assets_dir
        self._link_by_hash: dict[str, str] = {}
        self._next_index = 1

    def save(self, data: bytes, suffix: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        if digest in self._link_by_hash:
            return self._link_by_hash[digest]

        self.assets_dir.mkdir(parents=True, exist_ok=True)
        filename = f"image{self._next_index}{suffix}"
        self._next_index += 1
        (self.assets_dir / filename).write_bytes(data)

        link = f"{self.assets_dir.name}/{filename}"
        self._link_by_hash[digest] = link
        return link

    def remove_if_empty(self) -> None:
        """Clean up the assets folder if nothing was ever saved into it."""
        if self.assets_dir.exists() and not any(self.assets_dir.iterdir()):
            self.assets_dir.rmdir()


def dedupe_directory(assets_dir: Path) -> dict:
    """Delete any file in `assets_dir` that's byte-identical to another
    file already seen there, keeping the first copy encountered. Returns
    a {deleted_filename: kept_filename} map — apply it to any Markdown
    text with apply_renames() to fix up the now-dangling references."""
    renames: dict[str, str] = {}
    if not assets_dir.exists():
        return renames

    seen_hashes: dict[str, str] = {}
    for path in sorted(assets_dir.iterdir()):
        if not path.is_file():
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen_hashes:
            renames[path.name] = seen_hashes[digest]
            path.unlink()
        else:
            seen_hashes[digest] = path.name
    return renames


def apply_renames(text: str, renames: dict) -> str:
    """Rewrite references to a deleted duplicate filename to point at the
    canonical file that was kept in its place."""
    for old_name, new_name in renames.items():
        text = text.replace(old_name, new_name)
    return text
