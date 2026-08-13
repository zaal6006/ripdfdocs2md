# ripdfdocs2md — Project Audit Report

**Date:** 2026-08-12
**Scope:** Re-check everything discovered during development for gaps, fix the
image-export default per an updated requirement, and review the codebase for
quality/architecture issues.

**Result:** 19 source modules, 13 test files, **73 tests, all passing**
(re-run 3× consecutively to confirm stability, since one of today's own
findings was a test-isolation bug). Six real fixes went in during this audit
— not just observations, since several were quick and clearly worth doing
immediately. Details below.

---

## 1. Changes made during this audit

### 1.1 Image export default flipped to OFF
Per your correction, images are now **off by default**; pass `--images` to
extract them. This reverses the earlier decision (images on by default,
`--no-images` to opt out) — `cli.py`, tests, and `SETUP.md` are all updated.

### 1.2 Fixed an inconsistency this flip exposed
With images off, the PDF path already skipped images entirely — but the DOCX
path (via mammoth) fell back to embedding each image **inline as base64**,
which isn't "no images," it's a heavier way of including them (and bloats the
file). `docx_reader.py` now drops images entirely when `assets_dir` is `None`,
matching the PDF path. Verified: a DOCX with an embedded image now produces
byte-identical "no image trace" output whether the image is a PDF or a DOCX
source.

### 1.3 Worker error messages were useless — now fixed
Found while testing: converting a corrupt/invalid PDF produced this:
```
ERROR: Command '['...python.exe', '-m', 'ripdfdocs2md._pdf_checkbox_worker', ...]' returned non-zero exit status 1.
```
That tells a user nothing. The actual problem (visible in the worker's own
stderr) was `pymupdf.FileDataError: Failed to open file '...' as type pdf.`
— exactly what they'd need to diagnose it. Added a `WorkerError` exception in
`pdf_reader.py` that extracts the worker's real error and surfaces it:
```
ERROR: checkbox detection failed: pymupdf.FileDataError: Failed to open file '...' as type pdf.
```
Covered by a new test (`test_pdf_reader.py`).

### 1.4 Found and fixed a real test-suite bug (not just a code bug)
Adding `test_pdf_reader.py` (which imports `pdf_reader.py`, which imports
`pymupdf4llm`) caused `test_pdf_table_worker.py` to start **silently returning
wrong results** — the exact same `pymupdf4llm`-monkeypatches-`pymupdf`-globally
issue we spent real effort on for production code earlier in this project,
now biting the test suite itself, since pytest imports all test modules in one
process. `test_pdf_table_worker.py`'s tests now invoke the worker via a real
subprocess (matching how it's actually used in production) instead of calling
its functions in-process, making them immune to this regardless of what other
test files do. Confirmed stable across repeated full-suite runs.

*(The checkbox-worker tests turned out not to be affected — they don't use
`page.find_tables()`, the specific API that gets monkeypatched — but this is
worth knowing if that module's tests ever grow to depend on it.)*

### 1.5 Unified table-cell Markdown escaping
Found that `pdf_tables.py` (the ruling-line/ML table path) only escaped `|` in
cell text, while `borderless_tables.py` (built later, during the pdfmd review)
escaped a fuller set (backslash, backtick, `*`, `_`, `|`). Two independent
copies of "the same job," already drifted apart. Centralized into
`markdown_escape.py`, imported by both. New tests: `test_markdown_escape.py`.

### 1.6 Removed dead code
`pdf_reader.convert()` (the original, non-page-based PDF→Markdown function
from the very first step of this project) has been unused since page-based
processing was introduced — nothing calls it, and it's had no test coverage
this whole time. Removed.

### 1.7 Closed a real test-coverage gap
`cli.py` (the primary interface every user actually touches) and
`pdf_reader.py`'s error path had **zero** direct tests before today — all
validation had been manual CLI runs. Added `test_cli.py` (7 tests: single-file
conversion, batch/folder mode, collision-renaming, `.doc` skip behavior,
images-off-by-default, empty-input handling, summary-line accuracy) and
`test_pdf_reader.py` (1 test, described in 1.3).

### 1.8 Re-confirmed: no real data corruption anywhere
Did a fresh full regeneration of every sample file (with `--images`, to
exercise that path thoroughly too) and grepped every output file for the
Unicode replacement character (`�`). **Zero matches, everywhere.** This
reconfirms something noted earlier in the project: every `�` sighting during
development was a Windows console display artifact from my own diagnostic
`print()` calls (cp1252 can't render an en-dash), never actual corruption in
a real output file. Also spot-checked the two DOCX files reporting "0 images"
against their own zip contents — genuinely no embedded media, not a silent
extraction failure.

---

## 2. Feature status

| Feature | Status |
|---|---|
| PDF → Markdown (headings, bold/italic, lists) | ✅ Working |
| DOCX → Markdown | ✅ Working |
| Repeating header/footer removal | ✅ Working |
| Cross-page paragraph/hyphenation rejoining | ✅ Working |
| Letter-spaced heading rejoining (English + French) | ✅ Working |
| Ruled table detection & reconstruction | ✅ Working |
| Borderless (whitespace-only) table detection | ✅ Working |
| False-positive table guard (decorative cover graphics) | ✅ Working |
| Spurious strikethrough removal | ✅ Working |
| Heading word-fragmentation repair | ✅ Working (headings only — see §3) |
| Image export (off by default, `--images` to opt in) | ✅ Working |
| Image deduplication (exact byte match) | ✅ Working |
| Image link verification tool (`ripdfdocs2md-verify`) | ✅ Working |
| **Checkboxes — vector-drawn shapes** | ✅ Working |
| Checkboxes — dingbat-font glyphs (Wingdings/2/3, Webdings) | ❌ Not implemented |
| Checkboxes — interactive PDF form fields (AcroForm) | ❌ Not implemented |
| Legacy `.doc` auto-conversion | ❌ Not implemented (clear skip message + manual workaround) |
| Numeric collision-renaming for output files | ✅ Working |
| Per-document asset folders (safe for bulk/batch runs) | ✅ Working |

**On checkboxes specifically** (since you asked directly): vector-drawn
checkboxes — a small square outline, optionally with an X/checkmark inside —
are fully working and validated end-to-end against a real document, matching
every single one of its 15 checkboxes' checked/unchecked state exactly.
Dingbat-font checkboxes (a different mechanism entirely — a font character
with no real Unicode mapping) are a separate, not-yet-implemented case; see
§3.

---

## 3. Known limitations (already documented in SETUP.md, restated here for visibility)

- A table row split exactly across a PDF page boundary renders as two small
  tables instead of one (no data loss, just presented in two pieces).
- The heading word-fragmentation fix is scoped to headings only; the same
  fragmentation pattern occasionally leaks into a body-text sentence and is
  left alone (fixing it generally risks mangling emails/numbers nearby).
- Dingbat-font checkboxes (Wingdings/Wingdings2/Webdings) aren't recovered —
  a fundamentally different mechanism from the vector-drawn shapes that are
  handled. Only unchecked examples have been found in testing so far, so
  there's no confirmed "checked" glyph mapping to validate against yet.
- Interactive PDF form-field (AcroForm) checkboxes aren't handled.
- Legacy `.doc` files are skipped with a clear message and manual workaround,
  not auto-converted.

## 4. Newly found this session, not yet fixed

- **Decorative dingbat bullet/arrow glyphs render as stray literal
  characters.** In `incident-and-accident-report.pdf`, a font (Wingdings3)
  used purely for small arrow-icon bullets has no real Unicode mapping, so
  the extracted text shows a literal `X` or `tt` where the source PDF shows
  an icon — e.g. `###### X **SECTION A**` instead of `###### SECTION A`.
  Cosmetic only (nothing after the stray character is affected), confirmed
  still present, not fixed — this would be new scope (a different problem
  from the checkbox glyph work), so I flagged it rather than building a fix
  without checking with you first. Low effort if you want it addressed:
  a line starting with a heading/list marker followed immediately by an
  isolated `X`/`tt`-style token and then real content is a fairly safe,
  narrow pattern to detect and strip.

## 5. Code quality / architecture observations

- **The `pymupdf4llm`-monkeypatches-`pymupdf` issue is a recurring source of
  subtlety.** It broke table detection and text-spacing in production earlier
  in the project, and today it broke a *test's* correctness the same way.
  The fix pattern (run in an isolated subprocess) is sound and now applied
  consistently in production; just worth knowing this is a sharp edge that
  could resurface if a future test imports something `pymupdf4llm`-adjacent
  in-process again.
- **Performance**: each PDF conversion now spawns two subprocesses (checkbox
  worker, table worker), each with Python startup overhead (~100–300ms) on
  top of actual PDF parsing. Not a problem at the scale tested (a 35-page,
  image-heavy PDF converts in under a minute), but worth knowing if batch
  sizes grow much larger — the two workers could in principle be merged into
  one subprocess call to halve that fixed overhead, at some cost to the
  current clean separation of concerns.
- **`docx_reader.py` still has no dedicated unit tests** — it's exercised
  indirectly through `test_cli.py` and extensive manual runs against real
  files, but there's no focused test for e.g. its MIME-type-to-extension
  guessing or its image-skip behavior in isolation.
- **Exception handling in the CLI is intentionally broad** (`except
  Exception` around each file's conversion, so one bad file can't kill an
  entire batch run) — the right call for this tool, but it means a bug
  anywhere in the ~10-stage processing pipeline surfaces as a generic
  `ERROR: <message>` line. Today's `WorkerError` fix makes the two
  subprocess-related failure paths specifically readable; other exception
  types still just show Python's default message, which is usually fine but
  isn't uniformly curated.
- **The pipeline is a sequence of ~8 sequential post-processing passes**
  (table injection → borderless tables → strikethrough fix → heading
  fragments → ...) built incrementally, each added when a real document
  exposed a real gap. That's a reasonable way to have gotten here — every
  fix is grounded in a concrete, verified case rather than speculative
  design — but the *order* of these passes matters (e.g. strikethrough must
  be stripped before heading-fragment repair runs) and that dependency isn't
  written down in one place. Low risk today; worth a short comment next to
  the pass list in `pdf_reader.convert_pages()` if it grows further.

## 6. Open decisions for you

1. **Wingdings3 bullet/arrow glyph cleanup** (§4) — want this fixed now, or
   fine as a documented cosmetic limitation for the moment?
2. **Wingdings-family checkbox glyph mapping** — still unresearched/unbuilt.
   Worth prioritizing, or lower priority until a document with a *confirmed
   checked* dingbat glyph shows up to validate against?
3. Two smaller polish items surfaced during an earlier code review
   (numeric-column right-alignment in tables, and the cell-escaping gap now
   fixed in §1.5) were partially addressed — alignment inference specifically
   was never built. Worth doing, or skip?

Everything else from this session's development is either fixed, verified
working, or an explicitly documented known limitation — nothing else was
found sitting silently broken.
