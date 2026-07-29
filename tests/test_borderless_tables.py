from ripdfdocs2md.borderless_tables import convert_borderless_tables


def test_converts_whitespace_aligned_numeric_table():
    text = (
        "Country          Rate\n"
        "Canada           $80.00\n"
        "United States    $100.00\n"
        "Other            $100.00"
    )
    result = convert_borderless_tables(text)

    assert "| Country | Rate |" in result
    assert "|---|---|" in result
    assert "| Canada | $80.00 |" in result
    assert "| United States | $100.00 |" in result
    assert "| Other | $100.00 |" in result


def test_leaves_normal_prose_paragraph_untouched():
    text = (
        "This is a perfectly ordinary paragraph that describes the policy "
        "in plain prose, with more than five words and a period at the end."
    )
    assert convert_borderless_tables(text) == text


def test_leaves_bullet_list_untouched():
    text = "- Fast processing\n- Offline operation\n- Simple setup"
    assert convert_borderless_tables(text) == text


def test_leaves_existing_markdown_table_untouched():
    text = "| A | B |\n|---|---|\n| 1 | 2 |"
    assert convert_borderless_tables(text) == text


def test_leaves_heading_block_untouched():
    text = "# A Heading With Some Words"
    assert convert_borderless_tables(text) == text


def test_preserves_surrounding_blocks_and_only_converts_the_table():
    text = (
        "# Introduction\n\n"
        "This paragraph is just prose and should not become a table at all.\n\n"
        "Item          Qty        Price\n"
        "Widget        10         $5.00\n"
        "Gadget        3          $12.00\n\n"
        "# Conclusion"
    )
    result = convert_borderless_tables(text)

    assert "# Introduction" in result
    assert "# Conclusion" in result
    assert "This paragraph is just prose" in result
    assert "| Item | Qty | Price |" in result
    assert "| Widget | 10 | $5.00 |" in result


def test_does_not_misfire_on_short_two_line_block():
    text = "Yes\nNo"
    assert convert_borderless_tables(text) == text
