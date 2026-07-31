"""Read a DOCX file and return its content as Markdown text.

Uses mammoth to convert DOCX to clean HTML (preserving headings, bold,
italic, and lists), then markdownify to turn that HTML into Markdown.
"""

import mimetypes
from pathlib import Path

import mammoth
from markdownify import markdownify as html_to_markdown

from .image_export import ImageSaver

_DEFAULT_IMAGE_SUFFIX = ".png"


def convert(docx_path: Path, assets_dir: Path | None = None) -> str:
    """Convert a single DOCX file to a Markdown string.

    If `assets_dir` is given, embedded images are written there and
    linked into the Markdown as "<assets_dir.name>/imageN.ext" — relative
    to the folder the final .md file itself will live in (assets_dir's
    parent). Byte-identical images (e.g. a logo repeated on every page)
    are deduplicated down to a single shared file. If None, mammoth's
    default behavior (embedding images inline as base64 data URIs) is
    used instead.
    """
    saver = ImageSaver(assets_dir) if assets_dir is not None else None
    convert_image = mammoth.images.img_element(_make_image_converter(saver)) if saver else None

    with open(docx_path, "rb") as docx_file:
        result = mammoth.convert_to_html(docx_file, convert_image=convert_image)

    markdown = html_to_markdown(result.value, heading_style="ATX", bullets="-")

    if saver is not None:
        saver.remove_if_empty()

    return markdown


def _make_image_converter(saver: ImageSaver):
    def convert_image(image):
        with image.open() as image_bytes:
            data = image_bytes.read()
        suffix = mimetypes.guess_extension(image.content_type) or _DEFAULT_IMAGE_SUFFIX
        return {"src": saver.save(data, suffix)}

    return convert_image
