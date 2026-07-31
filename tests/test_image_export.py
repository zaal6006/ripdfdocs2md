from ripdfdocs2md.image_export import ImageSaver, apply_renames, dedupe_directory


def test_image_saver_writes_file_and_returns_relative_link(tmp_path):
    assets_dir = tmp_path / "report_assets"
    saver = ImageSaver(assets_dir)

    link = saver.save(b"fake png bytes", ".png")

    assert link == "report_assets/image1.png"
    assert (assets_dir / "image1.png").read_bytes() == b"fake png bytes"


def test_image_saver_deduplicates_identical_bytes(tmp_path):
    assets_dir = tmp_path / "report_assets"
    saver = ImageSaver(assets_dir)

    link1 = saver.save(b"same bytes", ".png")
    link2 = saver.save(b"same bytes", ".png")
    link3 = saver.save(b"different bytes", ".png")

    assert link1 == link2 == "report_assets/image1.png"
    assert link3 == "report_assets/image2.png"
    assert len(list(assets_dir.iterdir())) == 2


def test_image_saver_remove_if_empty(tmp_path):
    assets_dir = tmp_path / "report_assets"
    saver = ImageSaver(assets_dir)
    assets_dir.mkdir()

    saver.remove_if_empty()

    assert not assets_dir.exists()


def test_image_saver_remove_if_empty_leaves_nonempty_dir(tmp_path):
    assets_dir = tmp_path / "report_assets"
    saver = ImageSaver(assets_dir)
    saver.save(b"data", ".png")

    saver.remove_if_empty()

    assert assets_dir.exists()


def test_dedupe_directory_removes_duplicate_files(tmp_path):
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "a.png").write_bytes(b"logo")
    (assets_dir / "b.png").write_bytes(b"logo")
    (assets_dir / "c.png").write_bytes(b"unique")

    renames = dedupe_directory(assets_dir)

    remaining = sorted(p.name for p in assets_dir.iterdir())
    assert remaining == ["a.png", "c.png"]
    assert renames == {"b.png": "a.png"}


def test_dedupe_directory_on_missing_dir_returns_empty():
    assert dedupe_directory  # importable
    from pathlib import Path

    assert dedupe_directory(Path("/nonexistent/path/xyz")) == {}


def test_apply_renames_rewrites_text():
    text = "See ![](assets/b.png) and again ![](assets/b.png)."
    result = apply_renames(text, {"b.png": "a.png"})
    assert result == "See ![](assets/a.png) and again ![](assets/a.png)."
