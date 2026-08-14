# ripdfdocs2md — Setup & Usage Guide

Local, offline PDF/DOCX/DOC → Markdown converter. This guide covers installing it
from scratch, running it on a single file, running it in batch over a folder, and
running the test suite. No internet access is required at any point after the
one-time install below — no files are uploaded anywhere.

## 1. Prerequisites

- Windows 10/11
- Python 3.10 or newer ([python.org](https://www.python.org/downloads/) — check
  "Add python.exe to PATH" during install)
- Git (to clone the repo)
- **Only if you need to convert old `.doc` files**: LibreOffice (installed, or the
  no-install "Portable" build) — see section 8 for why and how to set it up. PDF and
  `.docx` conversion don't need this at all.

Check your Python version:

```bash
python --version
```

## 2. Get the code

```bash
git clone <repo-url> ripdfdocs2md
cd ripdfdocs2md
```

(If you already have the folder, just `cd` into it.)

## 3. Create a virtual environment

A virtual environment ("venv") keeps this project's Python packages isolated from
anything else on your machine — similar to how `node_modules` isolates a JS
project's dependencies.

```bash
python -m venv .venv
```

This creates a `.venv\` folder inside the project. It's already excluded from git
via `.gitignore` — never commit it.

## 4. Install the project and its dependencies

Install in **editable mode** (`-e`) with the `dev` extras (test tools):

```bash
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Editable mode means changes you make to the source code take effect immediately,
with no reinstall step needed.

This installs:

| Package | Purpose |
|---|---|
| `pymupdf4llm` | PDF → Markdown extraction |
| `mammoth` | DOCX → HTML extraction |
| `markdownify` | HTML → Markdown conversion |
| `wordninja-enhanced` | Fixes letter-spaced headings (English + French) |
| `pytest`, `python-docx` (dev only) | Running tests |

It also registers two commands inside `.venv\Scripts\`: `ripdfdocs2md` (the
converter) and `ripdfdocs2md-verify` (checks image links in already-converted
files — see section 7).

### Verify the install

```bash
.\.venv\Scripts\ripdfdocs2md.exe --help
```

You should see the usage text. If PowerShell can't find the command, always call it
with the full path as shown above — you do **not** need to activate the virtual
environment first.

## 5. Convert a single file

```bash
.\.venv\Scripts\ripdfdocs2md.exe "samples\some_file.pdf" -o output
```

This writes `output\some_file.md`. Works the same way for `.docx` and `.doc`:

```bash
.\.venv\Scripts\ripdfdocs2md.exe "samples\some_file.docx" -o output
.\.venv\Scripts\ripdfdocs2md.exe "samples\some_file.doc" -o output
```

Converting a `.doc` file needs LibreOffice available — see section 8 if you haven't
set that up yet.

`-o` / `--output-dir` is optional and defaults to `output\` in the current folder.

## 6. Convert a whole folder (batch mode)

Point it at a folder instead of a file — every `.pdf`, `.docx`, and `.doc` inside is
converted:

```bash
.\.venv\Scripts\ripdfdocs2md.exe samples -o output
```

You can also mix specific files and folders in one command:

```bash
.\.venv\Scripts\ripdfdocs2md.exe samples\a.pdf samples\some_folder -o output
```

Each input file `name.ext` produces `output\name.md`. If two input files would
produce the same output name (e.g. `report.pdf` and `report.docx`, or two
same-named files from different folders), the later one is automatically
renamed with a numeric suffix — `report_1.md`, `report_2.md`, ... — so neither
output silently overwrites the other.

### Reading the summary line

Every run ends with a line like:

```
Done: 6 converted, 0 failed, 2 skipped (unsupported format).
```

- **converted** — written successfully to `output\`
- **failed** — an unexpected error occurred while converting (see the `ERROR:` line
  above it for details)
- **skipped** — recognized as an unsupported format (see below) and not attempted

Exit code is `0` only when everything converted cleanly; `1` if anything failed or
was skipped — useful if you ever call this from a script.

## 7. Image export

Embedded images are **skipped by default** — the Markdown has just the text
content, nothing else. Pass `--images` to extract them instead:

```bash
.\.venv\Scripts\ripdfdocs2md.exe samples -o output --images
```

With `--images`, each output file gets its own `<name>_assets\` folder next to
it, and images are linked into the Markdown as relative paths:

```
output\
  report.md
  report_assets\
    report.pdf-0001-01.png
    report.pdf-0003-00.png
```

```markdown
![](report_assets/report.pdf-0001-01.png)
```

- **One folder per document** — even in a batch/bulk run, each file's images stay
  in their own folder (never a shared common pool), so nothing collides or gets
  mixed up between documents.
- **Deduplication**: if the exact same image appears more than once (e.g. a
  letterhead logo repeated on every page), only one copy is saved and every
  reference points to it. Images are compared by exact byte content — if two
  images are merely similar (not byte-identical, e.g. resized or recompressed),
  both are kept as-is rather than guessing they're "close enough."
- **Naming**: PDF images keep pymupdf4llm's own naming
  (`<pdf-filename>-<page>-<index>.png`); DOCX images are named sequentially
  (`image1.png`, `image2.png`, ...). Assets folder names are space-free
  (`My Report.pdf` → `My_Report_assets\`) even when the .md file's own name isn't
  — a workaround for a pymupdf4llm bug that crashes when its image-writing path
  contains a space.
- A document with no images produces no assets folder at all (nothing empty left
  behind).
- Without `--images`, images aren't embedded some other way either (e.g. inline
  as base64) — they're dropped entirely, for both PDF and DOCX. mammoth's own
  default behavior would otherwise inline each DOCX image as a base64 data URI
  when no image handling is configured; we override that so "off" really means
  no image content at all, consistent with the PDF path.

### Checking image extraction worked

A second command, `ripdfdocs2md-verify`, checks that every image link in a
converted file actually resolves to a real, valid image file — no need to open a
Markdown viewer just to confirm nothing's broken:

```bash
.\.venv\Scripts\ripdfdocs2md-verify.exe output
```

Run it against a single file or a whole folder (every `.md` inside gets checked).
It reports each broken reference and exits non-zero if anything's wrong:

```
output\report.md: 3 image link(s) - OK
output\other.md: 2 image link(s) - PROBLEMS
  MISSING: other_assets/other.pdf-0002-00.png

Some images are missing or invalid - see above.
```

"Invalid" means the file exists but its content doesn't match its extension
(e.g. a truncated or corrupted `.png`) — checked via the file's magic bytes, not
just whether it's non-empty. A `data:` URI (an image embedded inline as base64,
which shouldn't normally appear from this tool's own output — see section 7 —
but could show up in a hand-edited or otherwise-produced file) is counted but
never flagged, since it isn't a file reference at all.

To actually *see* the images (not just confirm the links resolve), the easiest
way is a Markdown viewer with a live preview — e.g. in VS Code, open the `.md`
file and press `Ctrl+Shift+V`. Since the file and its `_assets\` folder are
siblings on disk, any standard viewer resolves the relative links correctly.

## 8. `.doc` (old binary Word format) support

`.doc` (Word 97–2003 binary format) is a completely different file format from
`.docx`, and the library we use to read Word documents (`mammoth`) only understands
`.docx`. Instead of asking you to manually re-save every `.doc` file, the tool
converts it to `.docx` for you first, then runs the normal DOCX pipeline on the
result — this happens automatically and produces the same quality of Markdown
(headings, bold/italic, lists, tables) as a native `.docx` file.

That first conversion step is done by a headless LibreOffice — it isn't
pip-installable, so it's a separate one-time setup:

**Option A — you (or your IT department) already have LibreOffice installed.**
Nothing to do; the tool finds it automatically at its usual install location
(`C:\Program Files\LibreOffice\...`).

**Option B — no install / no admin rights.** Download "LibreOffice Portable" (the
no-install build) from
[portableapps.com](https://portableapps.com/apps/office/libreoffice_portable),
extract it anywhere (e.g. `C:\Tools\LibreOfficePortable`), then tell
`ripdfdocs2md` where to find it by setting an environment variable pointing at the
`soffice.exe` inside it:

```powershell
$env:RIPDFDOCS2MD_SOFFICE = "C:\Tools\LibreOfficePortable\App\libreoffice\program\soffice.exe"
```

(Set this permanently via Windows' "Environment Variables" system settings if you
don't want to re-run that line every new terminal session.)

If neither is set up, converting a `.doc` file fails with a clear `ERROR:` line
telling you to install LibreOffice or set `RIPDFDOCS2MD_SOFFICE` — PDF and `.docx`
conversion are completely unaffected either way.

## 9. What the converter fixes automatically

- **Headings, bold/italic, lists** are preserved as proper Markdown.
- **Repeating headers/footers** (running titles, page numbers, etc. that appear on
  almost every page) are detected and stripped.
- **Paragraphs split across a page boundary** (including hyphenated words cut in
  half, e.g. "compli-" / "cated") are rejoined into one sentence.
- **Letter-spaced headings** — titles styled with manual character-spacing, e.g.
  `R E P O R T A N D A N A LY S I S` — are detected and rejoined
  (`REPORT AND ANALYSIS`), using English and French dictionaries so it works for
  both languages without configuration.
- **Borderless tables** (PDF) — some tables have no vector-drawn border at all
  (plain whitespace-aligned columns). Since nothing about them is detectable
  from PDF ruling lines, we score each paragraph-like block of extracted text
  for "looks like a table" (consistent column count, numeric/short-token-heavy
  content vs. prose) and convert confident matches to Markdown tables. Adapted
  from the equivalent detector in the open-source
  [pdfmd](https://github.com/M1ck4/pdfmd) project.
- **Tables** (PDF) — pymupdf4llm's default ML layout engine sometimes
  misclassifies a bordered, form-style table (e.g. a 2-column policy header with
  checkboxes) as plain text, flattening it into one run-on paragraph, and even
  when it does classify a region as a table, PyMuPDF's own cell-boundary
  detection can be wrong for tables where the column divider is drawn as a
  separate line per row (common in office-generated PDFs) rather than one
  continuous line down the whole table. We rebuild these tables directly from
  the underlying ruling rectangles and text positions (in an isolated
  subprocess, so it never conflicts with the ML engine) and splice a correct
  Markdown table over the original region. Tables in DOCX files are already
  handled well by the underlying library and need no extra step.
  - Known limitation: if a single table row is split exactly across a PDF page
    boundary, it comes out as two separate small tables instead of one — no
    data is lost or garbled, it's just presented as two tables rather than one.
  - Known limitation: `find_tables()` occasionally mistakes a decorative
    cover-page graphic (background color blocks, shapes) for a table. We guard
    against this by requiring the candidate to actually overlap real text
    content the layout model recognized — if you ever see a cover page render
    as a mostly-empty table again, that's this edge case resurfacing.
- **Stylized headings/titles** (PDF) — pymupdf4llm's ML layout engine
  occasionally misreads a document's display font as strikethrough formatting
  (wrapping random word fragments in `~~like this~~`) or splits one heading
  across multiple bold spans with a spurious space at the split (e.g.
  `**THE DESJARDINS CEN** **TRE FOR ADV**` instead of one continuous
  `**THE DESJARDINS CENTRE FOR ADV**...`). We strip spurious strikethrough
  unconditionally (real strikethrough essentially never appears in these
  documents), and for headings specifically, rebuild the whole heading from
  word-frequency segmentation (the same technique used for letter-spaced
  titles) rather than trying to guess which individual gaps are wrong.
  - Known limitation: this heading fix is intentionally scoped to headings
    only (short, and never legitimately mix in emails/numbers) — the same
    kind of fragmentation occasionally leaks into a body-text sentence, and
    those are left as-is rather than risk mangling unrelated text nearby.
- **Checkboxes** (PDF) — a checkbox drawn as a vector shape (a small square
  outline, optionally with an X or checkmark inside) is invisible to text
  extraction entirely — it's not a font character, so it vanishes without a
  trace by default. We detect these (a checkbox-sized, roughly square cluster
  of line drawings with a text label immediately beside it — filtered against
  decorative graphics/icons by requiring the shape to be black/dark-neutral,
  not bold-styled, and genuinely adjacent to its label) and burn the correct
  `[ ]` (unchecked) or `[x]` (checked) in as real text at that exact position,
  in a throwaway copy of the PDF, before conversion — so it shows up
  automatically, correctly placed next to its label, in a table cell or
  ordinary paragraph text alike:
  ```markdown
  | Policy: [ ] New [x] Revised [ ] Reviewed | ... |
  ```
  - Known limitation: this only covers checkboxes drawn as vector shapes.
    Some PDF forms use dingbat-font glyphs (Wingdings/Wingdings2/Webdings)
    for checkboxes instead — a completely different mechanism this doesn't
    yet handle, and PDF interactive form-field checkboxes (AcroForm widgets)
    aren't handled either, though those are comparatively rare in a plain
    (non-fillable) PDF export.

- **Not yet handled**: some PDFs use a dingbat font (e.g. Wingdings3) purely for
  decorative bullet/arrow markers in headings and list items — since those fonts
  don't have a real Unicode mapping for the glyph, the character that lands in
  the extracted text is essentially arbitrary (observed: a literal `X` or `tt`
  where the source PDF shows a small arrow icon), e.g. `###### X **SECTION A**`
  instead of `###### SECTION A`. This is cosmetic — nothing after the stray
  character is affected — but it isn't stripped automatically today.

None of this requires any setup — it runs automatically as part of every
conversion.

## 10. Running the test suite

```bash
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

All tests should pass before you commit changes to the converter logic.

## 11. Folder reference

```
ripdfdocs2md\
  .venv\           virtual environment (not committed)
  src\ripdfdocs2md\  the actual package/source code
  tests\           automated tests (pytest)
  samples\         put test PDFs/DOCX/DOC here (gitignored — never commit real documents)
  output\          converted .md files land here (gitignored)
  pyproject.toml   project metadata + dependency list
  README.md        short project pitch
  SETUP.md         this file
```

## 12. Troubleshooting

- **`ripdfdocs2md` command not found in PowerShell`** — always call the full path,
  `.\.venv\Scripts\ripdfdocs2md.exe`, rather than relying on `Activate.ps1` (which
  PowerShell's execution policy sometimes blocks).
- **Garbled or missing characters in filenames printed to the console** — should no
  longer happen; the tool forces UTF-8 console output. If you still see this, let
  the team know.
- **A real document contains sensitive/patient information** — never commit it.
  `samples\` and `output\` are already excluded via `.gitignore`, along with any
  loose `*.pdf`/`*.docx` files anywhere in the repo.
- **`.doc` file fails with "No LibreOffice 'soffice' executable found"** — see
  section 8; either install LibreOffice or set the `RIPDFDOCS2MD_SOFFICE`
  environment variable to point at a portable build's `soffice.exe`.

## Not yet implemented

- Anything involving dingbat/symbol fonts (Wingdings/Wingdings2/Wingdings3/
  Webdings) that don't have a real Unicode mapping for their glyphs: checkbox
  recovery for checkboxes drawn this way (vector-drawn checkboxes *are* handled,
  see section 9), and stripping the stray character a decorative bullet/arrow
  glyph in one of these fonts leaves behind.
- Interactive PDF form-field (AcroForm) checkboxes.
