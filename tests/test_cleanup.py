from ripdfdocs2md.cleanup import (
    collapse_blank_lines,
    join_pages,
    remove_repeating_boilerplate,
)


def test_removes_repeating_header_and_footer():
    pages = [
        "ACME Manual\n\n# Chapter 1\n\nSome text.\n\nPage 1 of 3",
        "ACME Manual\n\nMore text here.\n\nPage 2 of 3",
        "ACME Manual\n\nEven more text.\n\nPage 3 of 3",
    ]
    cleaned = remove_repeating_boilerplate(pages)

    for page in cleaned:
        assert "ACME Manual" not in page
        assert "Page" not in page


def test_does_not_strip_image_links_that_look_like_repeating_boilerplate():
    # Different page numbers baked into each filename normalize to the
    # exact same fingerprint once digits are collapsed — must not be
    # mistaken for a repeating header/footer and stripped.
    pages = [
        "![](assets/report.pdf-0001-01.png)\n\nSome text on page 1.",
        "![](assets/report.pdf-0002-01.png)\n\nSome text on page 2.",
        "![](assets/report.pdf-0003-01.png)\n\nSome text on page 3.",
    ]
    cleaned = remove_repeating_boilerplate(pages)

    assert cleaned[0].startswith("![](assets/report.pdf-0001-01.png)")
    assert cleaned[1].startswith("![](assets/report.pdf-0002-01.png)")
    assert cleaned[2].startswith("![](assets/report.pdf-0003-01.png)")


def test_leaves_single_page_untouched():
    pages = ["ACME Manual\n\nOnly one page.\n\nPage 1 of 1"]
    assert remove_repeating_boilerplate(pages) == pages


def test_does_not_remove_repeated_body_content():
    # "Fast processing" repeats but is NOT in the header/footer zone
    # (it's buried among other lines), so it must survive.
    pages = [
        "Title A\n\nIntro\n\nFast processing\n\nMore detail\n\nFooter A",
        "Title B\n\nIntro\n\nFast processing\n\nOther detail\n\nFooter B",
    ]
    cleaned = remove_repeating_boilerplate(pages)
    assert all("Fast processing" in page for page in cleaned)


def test_joins_hyphenated_word_split_across_page_boundary():
    pages = ["This is a compli-", "cated setup."]
    assert join_pages(pages) == "This is a complicated setup.\n"


def test_joins_sentence_split_across_page_boundary():
    pages = ["The wizard will guide you through the", "next few steps."]
    assert join_pages(pages) == "The wizard will guide you through the next few steps.\n"


def test_does_not_join_when_previous_page_ends_a_sentence():
    pages = ["This sentence is complete.", "This is a new paragraph."]
    result = join_pages(pages)
    assert "This sentence is complete." in result
    assert "This is a new paragraph." in result
    assert "complete.This" not in result  # not glued together


def test_does_not_join_into_a_heading_or_list_item():
    pages = ["Some trailing text without punctuation", "# New Chapter"]
    result = join_pages(pages)
    assert "Some trailing text without punctuation" in result
    assert "# New Chapter" in result
    assert "punctuation#" not in result  # not glued together


def test_collapse_blank_lines():
    text = "A\n\n\n\n\nB"
    assert collapse_blank_lines(text) == "A\n\nB"
