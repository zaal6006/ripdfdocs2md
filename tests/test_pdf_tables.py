from ripdfdocs2md.pdf_tables import inject_tables_into_page_text


def test_replaces_flattened_text_block_with_markdown_table():
    text = "intro\n\nPolicy title: Foo Policy number: BAR\n\n# Next Heading\n\nmore text"
    table_start = text.index("Policy title")
    table_end = text.index("\n\n# Next Heading")

    page_boxes = [
        {"bbox": [0, 0, 10, 10], "pos": [0, table_start]},
        {"bbox": [0, 20, 500, 60], "pos": [table_start, table_end]},
        {"bbox": [0, 70, 10, 80], "pos": [table_end, len(text)]},
    ]
    tables = [{"bbox": [0, 20, 500, 60], "rows": [["Policy title: Foo", "Policy number: BAR"]]}]

    result = inject_tables_into_page_text(text, page_boxes, tables)

    assert "| Policy title: Foo | Policy number: BAR |" in result
    assert "Policy title: Foo Policy number: BAR" not in result
    assert "# Next Heading" in result
    assert "more text" in result


def test_leaves_text_untouched_when_no_page_boxes():
    text = "some flattened text"
    assert inject_tables_into_page_text(text, None, [{"bbox": [0, 0, 1, 1], "rows": [["a", "b"]]}]) == text


def test_leaves_text_untouched_when_no_tables():
    text = "some plain text"
    page_boxes = [{"bbox": [0, 0, 10, 10], "pos": [0, len(text)]}]
    assert inject_tables_into_page_text(text, page_boxes, []) == text


def test_leaves_text_untouched_when_table_bbox_does_not_overlap_any_box():
    text = "unrelated text"
    page_boxes = [{"bbox": [0, 0, 10, 10], "pos": [0, len(text)]}]
    tables = [{"bbox": [1000, 1000, 1010, 1010], "rows": [["a", "b"]]}]
    assert inject_tables_into_page_text(text, page_boxes, tables) == text


def test_handles_ragged_rows_and_none_cells():
    text = "block"
    page_boxes = [{"bbox": [0, 0, 10, 10], "pos": [0, len(text)]}]
    tables = [{"bbox": [0, 0, 10, 10], "rows": [["a", "b", "c"], ["only one", None]]}]

    result = inject_tables_into_page_text(text, page_boxes, tables)

    assert "| a | b | c |" in result
    assert "| only one |  |  |" in result


def test_escapes_pipe_characters_and_converts_newlines_to_br():
    text = "block"
    page_boxes = [{"bbox": [0, 0, 10, 10], "pos": [0, len(text)]}]
    tables = [{"bbox": [0, 0, 10, 10], "rows": [["a|b", "line1\nline2"]]}]

    result = inject_tables_into_page_text(text, page_boxes, tables)

    assert "a\\|b" in result
    assert "line1<br>line2" in result
