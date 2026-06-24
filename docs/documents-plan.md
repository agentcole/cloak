# Plan: document support (docling)

> **Status: proposed.** This is an implementation plan for review, not shipped
> behaviour. It adds a new input/output pillar to cloak — parsing whole
> documents (PDF/DOCX/PPTX/HTML/images) for scan, reversible masking, and
> one-way redaction — behind an optional `cloak-llm[docling]` extra.

## 1. Goals (decided)

| Decision | Choice |
|----------|--------|
| Use case | **Both**: detect-and-report (`scan`) *and* masking; reversible *and* one-way. |
| Output formats | **Open**: markdown, JSON, PDF, DOCX. |
| Packaging | **Optional extra** `[docling]`, lazy-imported (core stays zero-dep). |
| Surfaces | CLI, library API, MCP, proxy. |
| PDF/DOCX render | **Both modes**: in-place (preserve layout) *and* regenerate-from-structure. |
| Reversibility | **Two explicit modes**: `mask` (reversible, vault) vs `redact` (one-way). |
| OCR | **Optional**, behind a flag (docling EasyOCR/Tesseract pipeline). |
| PDF engine | **PyMuPDF (fitz)** for in-place redaction + bbox work. |

## 2. The central problem

cloak's pipeline is built on **flat strings + character offsets** (`Entity.start/end`,
right-to-left span replacement, `Vault.restore` by string match). Docling produces a
**structured `DoclingDocument`** with nodes, reading order, pages, and bounding boxes.

If we export docling → markdown and mask *that flattened string*, masking works but the
offsets no longer map back to page coordinates, so **in-place PDF redaction is impossible**.

**Design rule:** mask each *segment* individually into **one shared vault**, never the
flattened export. The shared vault preserves coreference (`[PERSON_1]` consistent across
all pages); per-segment provenance preserves the bbox needed for in-place redaction.

## 3. The bridge data structure

```python
@dataclass(frozen=True)
class Segment:
    text: str            # the segment's plain text (what cloak masks)
    node_id: str         # DoclingDocument node ref (for structure-aware re-emit)
    page: int | None     # 1-based page index (None for non-paginated inputs)
    bbox: tuple[float, float, float, float] | None  # (x0, y0, x1, y1) in PDF points
    order: int           # reading-order index
    kind: str            # "text" | "heading" | "table_cell" | "list_item" | ...

@dataclass
class SegmentedDoc:
    segments: list[Segment]
    source_path: str
    backend: str                 # "docling"
    raw: Any = None              # the underlying DoclingDocument (for JSON/regenerate)
```

`SegmentedDoc` is the single intermediate every renderer consumes. It is
dependency-free in shape (plain dataclasses), so it can live in `cloak/documents/types.py`
without dragging docling into the import graph.

## 4. New package layout

```
src/cloak/documents/
  __init__.py          # lazy re-exports; raises a clean "install [docling]" on miss
  types.py             # Segment, SegmentedDoc, DocumentResult  (no heavy deps)
  parser.py            # DocumentParser protocol + DoclingParser backend
  masker.py            # SegmentedDoc -> (masked SegmentedDoc, Vault), shared vault
  renderers/
    __init__.py        # registry: format -> renderer
    markdown.py        # masked segments -> markdown                 (reversible)
    json_.py           # masked DoclingDocument JSON                 (reversible)
    pdf.py             # PyMuPDF: in-place redaction OR regenerate
    docx.py            # python-docx regenerate; in-place via doc XML
```

### Parser protocol

```python
class DocumentParser(Protocol):
    def parse(self, path: str, *, ocr: bool = False) -> SegmentedDoc: ...
    def available(self) -> bool: ...      # mirrors Detector.available() pattern
```

`DoclingParser` flips docling's `PdfPipelineOptions.do_ocr` for the OCR flag, walks
`document.iterate_items()` to build `Segment`s, and carries each item's `prov` bbox.

## 5. Masking flow

```python
def mask_document(doc: SegmentedDoc, cloak: Cloak, *, mode="mask") -> DocumentResult:
    vault = Vault(salt=cloak._salt())          # one vault for the whole document
    masked_segments, entities = [], []
    for seg in doc.segments:
        res = cloak.mask_text(seg.text, vault)  # SHARED vault -> coreference
        masked_segments.append(replace(seg, text=res.text))
        entities.extend(_offset_entities(res.entities, seg))  # keep bbox provenance
    return DocumentResult(SegmentedDoc(masked_segments, ...), vault, entities)
```

- `mode="mask"` → uses the policy's strategy (placeholder/pseudonym/hash); vault is
  reversible. **Restore acts on the LLM's text answer, never on the binary file** —
  there is no "un-redact a PDF". The masked PDF/DOCX is a terminal artifact you hand to
  the model; the vault re-inflates the model's textual response.
- `mode="redact"` → forces the `redact` strategy; PII removed; no recoverable entries.

`scan_document` is the same walk without replacement — returns `list[Entity]` carrying
`page`/`bbox` so a report can say *"SSN on page 3"*.

## 6. Renderers

| Format | Mode | Mechanism | Fidelity |
|--------|------|-----------|----------|
| markdown | both | re-emit masked segments in reading order | structure (headings/tables) preserved, no layout |
| json | both | masked `DoclingDocument` → `.export_to_dict()` | full structure, machine-readable |
| pdf (regenerate) | both | build fresh PDF from masked structure | layout approximate |
| pdf (in-place) | both | **PyMuPDF** per-segment bbox | layout exact |
| docx (regenerate) | both | python-docx from structure | layout approximate |
| docx (in-place) | both | edit document XML runs | layout exact |

### In-place PDF redaction (the hard part — PyMuPDF)

```python
page.add_redact_annot(quad, text=token, fill=(0,0,0))  # token="" for pure redact
page.apply_redactions()        # ACTUALLY removes underlying text, not just a box
doc.scrub()                    # strip metadata, embedded files, hidden text
```

`apply_redactions()` deletes the covered glyphs from the content stream — essential so PII
isn't recoverable by copy-paste. For `mode="mask"` we pass the placeholder token as
replacement text; for `mode="redact"` we leave a black box.

**Known granularity limit:** docling reliably exposes **item/line-level** bboxes; per-word
boxes exist only for OCR'd content. So redacting "just the SSN inside a sentence" may
redact the whole line, or fall back to a word-box heuristic (split the line bbox by the
entity's character ratio). Ship **line-level first**, document it as a limitation, refine
to word-level where word boxes are available.

## 7. Engine API

```python
cloak.scan_document(path, *, ocr=False) -> list[Entity]
cloak.mask_document(path, *, ocr=False, mode="mask") -> DocumentResult

# DocumentResult
.vault                                  # reversible mapping (mask mode)
.entities                               # with page/bbox provenance
.to_markdown() -> str
.to_json() -> dict
.to_pdf(render="in-place"|"regenerate") -> bytes
.to_docx(render="in-place"|"regenerate") -> bytes
```

## 8. CLI

`_read_input` grows file-type sniffing (extension + magic bytes). Document paths route to
the document pipeline; text/stdin keeps today's behaviour unchanged.

```
cloak scan report.pdf --json                       # detect-and-report, page-aware
cloak mask report.pdf --format md   --vault v.json # reversible, markdown out
cloak mask report.pdf --format pdf  --render in-place --mode redact --ocr
cloak mask scan.pdf   --format pdf  --render in-place --ocr   # scanned doc
```

New flags (mask/scan): `--format md|json|pdf|docx`, `--render in-place|regenerate`,
`--mode mask|redact`, `--ocr`. Binary outputs require `-o/--out FILE` (no binary to stdout).

## 9. MCP & proxy

- **MCP**: add a `mask_document` tool — accepts a path or base64 bytes + format/mode/ocr,
  returns masked content (text formats inline; binary as base64) and a vault handle reusing
  the existing bounded MCP vault store.
- **Proxy**: detect `multipart/form-data` uploads, parse → mask → forward. Lowest priority
  (least natural fit); gate behind a config flag.

## 10. Packaging

```toml
[project.optional-dependencies]
docling = [
    "docling>=2.0.0",        # parsing; pulls torch + layout/OCR models
    "pymupdf>=1.24.0",       # in-place PDF redaction  (AGPL — see note)
    "python-docx>=1.1.0",    # docx regenerate / edit
]
```

Lazy-imported like `[ner]`; missing → clean *"install cloak-llm[docling]"* message, core
stays zero-dep. `[docling]` will be by far the heaviest extra (hundreds of MB of models +
cold start on first parse); OCR adds more.

**License note:** PyMuPDF is **AGPL-3.0**. cloak is Apache-2.0. Keeping PyMuPDF as an
*optional, user-installed* extra (not bundled, not a hard dep) means cloak's own
distribution stays Apache-2.0; users who install `[docling]` opt into AGPL themselves.
Flag in README/SECURITY and keep all `fitz` imports inside `documents/renderers/pdf.py`.

## 11. Testing

- Tiny fixture docs in `tests/fixtures/` (a 1-page text PDF, a scanned-image PDF, a DOCX).
- `scan_document` finds known PII with correct page numbers.
- `mask_document` round-trips: mask → restore the *text* answer via vault.
- In-place redaction: assert the underlying glyphs are gone (extract text from the output
  PDF, confirm the PII string is absent) — not merely visually covered.
- Coreference across pages (same value → same token on page 1 and page 5).
- Graceful skip when `[docling]` absent (mirrors NER unavailable tests).
- docling/OCR tests opt-in via env flag (`CLOAK_TEST_DOCLING=1`) like the GLiNER/Ollama tests.

## 12. Build order

1. **Parser + `SegmentedDoc` + markdown/json renderers + `scan_document`/`mask_document`
   (reversible).** Highest value, no PDF-render risk. Validates the offset→segment model.
2. **CLI wiring + `[docling]` extra + tests + OCR flag.**
3. **PDF/DOCX regenerate mode** (easier; no bbox).
4. **PDF/DOCX in-place redaction** (PyMuPDF, bbox mapping, `apply_redactions`, `scrub`) —
   hardest, isolated last.
5. **MCP tool**, then **proxy upload handling**.

## 13. Risks

| Risk | Mitigation |
|------|------------|
| Sub-line bbox granularity | line-level first + documented; word-box refinement later. |
| Heavy deps / cold start | optional extra, lazy import, clear install message. |
| PyMuPDF AGPL vs Apache-2.0 | optional user-installed extra; imports quarantined; documented. |
| "Reversible PDF" misread | docs make explicit: vault restores the *text answer*, not the file. |
| Incomplete text removal | use `apply_redactions()` + `scrub()`; test that glyphs are gone. |
| Scope creep vs ROADMAP | add an explicit ROADMAP item (this is a deliberate new pillar). |
