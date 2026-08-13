from ripdfdocs2md.markdown_escape import escape_markdown_cell


def test_escapes_pipe():
    assert escape_markdown_cell("a|b") == "a\\|b"


def test_escapes_asterisk_and_underscore():
    assert escape_markdown_cell("*bold* _italic_") == "\\*bold\\* \\_italic\\_"


def test_escapes_backtick():
    assert escape_markdown_cell("`code`") == "\\`code\\`"


def test_escapes_backslash_first_to_avoid_double_escaping():
    assert escape_markdown_cell("a\\b") == "a\\\\b"


def test_leaves_plain_text_untouched():
    assert escape_markdown_cell("Plain text, no specials.") == "Plain text, no specials."
