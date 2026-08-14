"""Read a legacy binary .doc file and return its content as Markdown text.

mammoth (used for .docx, see docx_reader.py) can't read the old Word
97-2003 binary format at all, and no mature pure-Python parser for it
exists. Instead we shell out to a headless LibreOffice, which has by far
the most mature .doc import filter available, to convert .doc -> .docx
first, then hand the result to docx_reader unchanged.
"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from . import docx_reader

_ENV_VAR = "RIPDFDOCS2MD_SOFFICE"
_COMMON_INSTALL_PATHS = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
]
# LibreOffice's own filter-name guessing from a bare "--convert-to docx"
# picks the wrong export filter for some legacy .doc files (observed:
# browser-saved "Web Page, Filtered" .doc files get misdetected as
# Writer/Web and then produce "no export filter" instead of a .docx) —
# spelling out the filter explicitly avoids that.
_DOCX_FILTER = "docx:MS Word 2007 XML"


class SofficeNotFoundError(RuntimeError):
    """Raised when no LibreOffice `soffice` executable can be located."""


class DocConversionError(RuntimeError):
    """Raised when the .doc -> .docx conversion subprocess fails."""


def convert(doc_path: Path, assets_dir: Path | None = None) -> str:
    """Convert a single legacy .doc file to a Markdown string.

    See docx_reader.convert for `assets_dir` semantics — once converted
    to .docx, this is just a thin pass-through into that pipeline.
    """
    soffice = find_soffice()
    doc_path = Path(doc_path)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        _run_soffice_convert(soffice, doc_path, out_dir=tmp_path, profile_dir=tmp_path / "profile")

        docx_path = tmp_path / (doc_path.stem + ".docx")
        if not docx_path.exists():
            raise DocConversionError(
                f"LibreOffice did not produce a .docx for {doc_path.name} "
                "(no error was reported, but the output file is missing)."
            )
        return docx_reader.convert(docx_path, assets_dir)


def find_soffice() -> str:
    """Locate a `soffice` executable.

    Checked in order: an explicit override via the RIPDFDOCS2MD_SOFFICE
    environment variable (set this if you're using a portable LibreOffice
    extracted somewhere with no installer involved), a standard Program
    Files install, then whatever's on PATH.
    """
    override = os.environ.get(_ENV_VAR)
    if override:
        if not Path(override).is_file():
            raise SofficeNotFoundError(f"{_ENV_VAR} is set to '{override}' but that file doesn't exist.")
        return override

    for candidate in _COMMON_INSTALL_PATHS:
        if Path(candidate).is_file():
            return candidate

    on_path = shutil.which("soffice") or shutil.which("soffice.exe")
    if on_path:
        return on_path

    raise SofficeNotFoundError(
        "No LibreOffice 'soffice' executable found - .doc conversion needs one. "
        "Install LibreOffice, or download the portable build (no install required) "
        f"and point the {_ENV_VAR} environment variable at its soffice.exe."
    )


def _run_soffice_convert(soffice: str, doc_path: Path, out_dir: Path, profile_dir: Path) -> None:
    # A fresh -env:UserInstallation per conversion avoids profile-lock
    # contention between overlapping runs; LibreOffice creates the folder
    # itself, it doesn't need to exist beforehand.
    args = [
        soffice,
        "--headless",
        "--norestore",
        f"-env:UserInstallation={profile_dir.as_uri()}",
        "--convert-to",
        _DOCX_FILTER,
        "--outdir",
        str(out_dir),
        str(doc_path),
    ]
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if result.returncode != 0:
        last_line = next(
            (line for line in reversed(result.stderr.splitlines()) if line.strip()),
            "(no error output)",
        )
        raise DocConversionError(f"LibreOffice conversion failed: {last_line}")
