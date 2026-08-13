import pytest

from ripdfdocs2md.pdf_reader import WorkerError, convert_pages


def test_corrupt_pdf_raises_informative_error(tmp_path):
    fake_pdf = tmp_path / "not_really_a_pdf.pdf"
    fake_pdf.write_text("this is not a PDF file at all", encoding="utf-8")

    with pytest.raises(WorkerError) as exc_info:
        convert_pages(fake_pdf)

    message = str(exc_info.value)
    # must name the actual problem, not just "non-zero exit status" —
    # that's the whole point of WorkerError over a bare CalledProcessError
    assert "non-zero exit status" not in message
    assert "Failed to open" in message or "FileDataError" in message
