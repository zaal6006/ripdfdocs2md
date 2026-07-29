from ripdfdocs2md.strikethrough_fix import remove_spurious_strikethrough


def test_unwraps_mid_word_strikethrough():
    text = "The Desjardins Centre helps trainees at The I ~~nstitute~~ build careers."
    result = remove_spurious_strikethrough(text)
    assert "~~" not in result
    assert "nstitute" in result  # unwrap only; does not attempt to rejoin the space


def test_unwraps_heading_with_nested_underline():
    text = "## **THE DESJARDINS CEN** **~~<u>TRE FOR</u>~~ ADV** **~~ANCED~~ TRA** **~~<u>INING</u>~~**"
    result = remove_spurious_strikethrough(text)
    assert "~~" not in result
    assert "<u>TRE FOR</u>" in result  # underline itself is left alone


def test_leaves_text_without_strikethrough_untouched():
    text = "A perfectly normal sentence with **bold** and *italic* and <u>underline</u>."
    assert remove_spurious_strikethrough(text) == text


def test_unwraps_multiple_spans_in_one_line():
    text = "~~are~~ **~~required~~ to com** **~~plete certain m~~ andat** **~~ory training~~ courses**"
    result = remove_spurious_strikethrough(text)
    assert "~~" not in result
    assert "are" in result and "required" in result and "andat" in result
