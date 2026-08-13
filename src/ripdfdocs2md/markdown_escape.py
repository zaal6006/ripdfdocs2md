"""Escaping for plain text going into a Markdown table cell.

Shared by pdf_tables.py (ruling-line/ML-detected tables) and
borderless_tables.py (whitespace-detected tables) — two independent
table-building strategies that both need the same escaping, so it lives
in one place rather than risking the two copies drifting apart (as they
already had: one escaped only "|", the other also escaped backslash,
backtick, "*", and "_").
"""

_ESCAPE_CHARS = ("\\", "`", "*", "_", "|")


def escape_markdown_cell(text: str) -> str:
    """Escape characters that would otherwise be misread as Markdown
    formatting or a table-column separator inside a cell's plain text.
    Order matters: backslash must be escaped first, or the backslashes
    this itself inserts for the other characters would get escaped too."""
    for ch in _ESCAPE_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text
