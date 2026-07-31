from ripdfdocs2md.verify import verify_file

_PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"rest of a fake png"


def test_all_images_present_and_valid(tmp_path):
    assets = tmp_path / "report_assets"
    assets.mkdir()
    (assets / "image1.png").write_bytes(_PNG_BYTES)

    md = tmp_path / "report.md"
    md.write_text("Some text.\n\n![](report_assets/image1.png)\n", encoding="utf-8")

    result = verify_file(md)

    assert result.ok
    assert result.total_links == 1
    assert result.missing == []
    assert result.invalid == []


def test_detects_missing_image(tmp_path):
    md = tmp_path / "report.md"
    md.write_text("![](report_assets/does_not_exist.png)\n", encoding="utf-8")

    result = verify_file(md)

    assert not result.ok
    assert result.missing == ["report_assets/does_not_exist.png"]


def test_detects_invalid_image_content(tmp_path):
    assets = tmp_path / "report_assets"
    assets.mkdir()
    (assets / "image1.png").write_bytes(b"this is not a real png file")

    md = tmp_path / "report.md"
    md.write_text("![](report_assets/image1.png)\n", encoding="utf-8")

    result = verify_file(md)

    assert not result.ok
    assert result.invalid == ["report_assets/image1.png"]


def test_no_image_links_is_ok(tmp_path):
    md = tmp_path / "report.md"
    md.write_text("Just plain text, no images here.\n", encoding="utf-8")

    result = verify_file(md)

    assert result.ok
    assert result.total_links == 0


def test_data_uri_is_counted_but_never_flagged(tmp_path):
    md = tmp_path / "report.md"
    md.write_text("![](data:image/png;base64,iVBORw0KGgoAAAANSU==)\n", encoding="utf-8")

    result = verify_file(md)

    assert result.ok
    assert result.total_links == 1
    assert result.missing == []
    assert result.invalid == []


def test_handles_multiple_links_mixed_results(tmp_path):
    assets = tmp_path / "report_assets"
    assets.mkdir()
    (assets / "good.png").write_bytes(_PNG_BYTES)

    md = tmp_path / "report.md"
    md.write_text(
        "![](report_assets/good.png)\n\n![](report_assets/missing.png)\n",
        encoding="utf-8",
    )

    result = verify_file(md)

    assert not result.ok
    assert result.total_links == 2
    assert result.missing == ["report_assets/missing.png"]
    assert result.invalid == []
