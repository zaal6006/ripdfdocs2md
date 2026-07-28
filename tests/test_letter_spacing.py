from ripdfdocs2md.letter_spacing import fix_letter_spacing


def test_fixes_letter_spaced_bold_heading():
    line = "# **R E P O R T A N D A N A LY S I S** "
    assert fix_letter_spacing(line).strip() == "# **REPORT AND ANALYSIS**"


def test_leaves_normal_heading_untouched():
    line = "## **OCCUPATIONAL HEALTH AND SAFETY DEPARTMENT** "
    assert fix_letter_spacing(line) == line


def test_leaves_normal_paragraph_untouched():
    text = "This is a simple paragraph that describes the product."
    assert fix_letter_spacing(text) == text


def test_leaves_short_line_untouched():
    # Only 2 tokens: below the minimum-token gate, should not be touched
    # even though both tokens are short.
    line = "A B"
    assert fix_letter_spacing(line) == line


def test_does_not_touch_lines_with_numbers_or_punctuation():
    line = "Tel.: 514 934-1934 ext. 42385 (Reception)"
    assert fix_letter_spacing(line) == line
