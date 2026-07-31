"""Small helpers shared by the package's command-line entry points."""

import sys


def use_utf8_console() -> None:
    """Windows terminals often default to a legacy codepage (e.g. cp1252)
    that can't encode many filenames (accents, Cyrillic, etc.). Force
    UTF-8 output so an unusual filename can't crash the whole run."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
