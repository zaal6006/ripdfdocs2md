# ripdfdocs2md — Setup & Usage Guide

Local, offline PDF/DOCX → Markdown converter. This guide covers installing it from
scratch, running it on a single file, running it in batch over a folder, and running
the test suite. No internet access is required at any point after the one-time
install below — no files are uploaded anywhere.

## 1. Prerequisites

- Windows 10/11
- Python 3.10 or newer ([python.org](https://www.python.org/downloads/) — check
  "Add python.exe to PATH" during install)
- Git (to clone the repo)

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

It also registers a `ripdfdocs2md` command inside `.venv\Scripts\`.

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

This writes `output\some_file.md`. Works the same way for `.docx`:

```bash
.\.venv\Scripts\ripdfdocs2md.exe "samples\some_file.docx" -o output
```

`-o` / `--output-dir` is optional and defaults to `output\` in the current folder.

## 6. Convert a whole folder (batch mode)

Point it at a folder instead of a file — every `.pdf` and `.docx` inside is
converted:

```bash
.\.venv\Scripts\ripdfdocs2md.exe samples -o output
```

You can also mix specific files and folders in one command:

```bash
.\.venv\Scripts\ripdfdocs2md.exe samples\a.pdf samples\some_folder -o output
```

Each input file `name.ext` produces `output\name.md`. If two input files share the
same name but have different extensions (e.g. `report.pdf` and `report.docx`), the
second one is automatically renamed `report__docx.md` so neither output silently
overwrites the other.

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

## 7. Known limitation: old `.doc` files are not supported

`.doc` (Word 97–2003 binary format) is a completely different file format from
`.docx`, and the library we use to read Word documents (`mammoth`) only understands
`.docx`. The tool detects `.doc` files and skips them with a clear message rather
than crashing:

```
Skipping some_file.doc: old .doc format not supported (see README).
```

**Workaround:** open the file in Word (or LibreOffice, if you don't have Word),
then **File → Save As → Word Document (.docx)**, and re-run the converter on the
new `.docx` file.

## 8. What the converter fixes automatically

- **Headings, bold/italic, lists** are preserved as proper Markdown.
- **Repeating headers/footers** (running titles, page numbers, etc. that appear on
  almost every page) are detected and stripped.
- **Paragraphs split across a page boundary** (including hyphenated words cut in
  half, e.g. "compli-" / "cated") are rejoined into one sentence.
- **Letter-spaced headings** — titles styled with manual character-spacing, e.g.
  `R E P O R T A N D A N A LY S I S` — are detected and rejoined
  (`REPORT AND ANALYSIS`), using English and French dictionaries so it works for
  both languages without configuration.

None of this requires any setup — it runs automatically as part of every
conversion.

## 9. Running the test suite

```bash
.\.venv\Scripts\python.exe -m pytest tests\ -v
```

All tests should pass before you commit changes to the converter logic.

## 10. Folder reference

```
ripdfdocs2md\
  .venv\           virtual environment (not committed)
  src\ripdfdocs2md\  the actual package/source code
  tests\           automated tests (pytest)
  samples\         put test PDFs/DOCX here (gitignored — never commit real documents)
  output\          converted .md files land here (gitignored)
  pyproject.toml   project metadata + dependency list
  README.md        short project pitch
  SETUP.md         this file
```

## 11. Troubleshooting

- **`ripdfdocs2md` command not found in PowerShell`** — always call the full path,
  `.\.venv\Scripts\ripdfdocs2md.exe`, rather than relying on `Activate.ps1` (which
  PowerShell's execution policy sometimes blocks).
- **Garbled or missing characters in filenames printed to the console** — should no
  longer happen; the tool forces UTF-8 console output. If you still see this, let
  the team know.
- **A real document contains sensitive/patient information** — never commit it.
  `samples\` and `output\` are already excluded via `.gitignore`, along with any
  loose `*.pdf`/`*.docx` files anywhere in the repo.

## Not yet implemented

- Image export to an `_assets\` folder (planned next).
- Automatic conversion of legacy `.doc` files.
