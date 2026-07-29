from ripdfdocs2md.heading_fragments import fix_heading_fragments


def test_rejoins_two_fragment_heading():
    line = "## **INTRODUCTIO** **N** "
    assert fix_heading_fragments(line).strip() == "## **INTRODUCTION**"


def test_rejoins_many_fragment_heading_with_nested_underline():
    # mirrors real output after strikethrough_fix.py has already run
    line = "## **THE DESJARDINS CEN** **<u>TRE FOR</u> ADV** **ANCED TRA** **<u>INING</u>** "
    result = fix_heading_fragments(line)
    assert result.strip() == "## **THE DESJARDINS CENTRE FOR ADVANCED TRAINING**"


def test_rejoins_fragment_split_across_internal_fragment_boundary():
    # "L" (end of frag1) + "AND" + "S" (both of frag2) + "CAPE" (frag3) -> "LANDSCAPE"
    line = "## **RESEARCH L** **AND S** **<u>CAPE</u>** "
    assert fix_heading_fragments(line).strip() == "## **RESEARCH LANDSCAPE**"


def test_leaves_already_correct_heading_mostly_alone():
    line = "## **GETTING STARTED** "
    # single fragment: regex requires 2+, so untouched
    assert fix_heading_fragments(line) == line


def test_leaves_non_heading_lines_untouched():
    line = "This is a normal paragraph with **bold** text, not a heading."
    assert fix_heading_fragments(line) == line


def test_skips_heading_containing_email_or_punctuation():
    line = "##### **To request access, complete the sign** **<u>up form. For inquiries, contact lise.sirois@muhc.mcgill.ca.</u>** "
    assert fix_heading_fragments(line) == line


def test_leaves_multi_word_body_text_with_bold_fragments_untouched():
    text = "As a new trainee you are **required to com** **plete certain m** **andat** **ory training**."
    assert fix_heading_fragments(text) == text
