---
name: nizam-corpus
description: Rules for the Nizam-e-Qanoon corpus and ingestion layer (L1) — scraping Pakistani statutes and judgments, PDF text extraction, provision-tree segmentation, footnote and amendment enrichment, the fourteen legal edge types, faceted classification, and the seven QA gates. Load when working on scrapers, parsers, segmentation, OCR, the curation console, legal taxonomy, or anything under data/ or corpus/.
---

# Nizam-e-Qanoon — corpus and ingestion

**Reference:** `docs/02-corpus-and-ingestion.html` (pipeline, gates, sources) · `docs/03b-legal-data-model.html` (edges, facets, schedules)
**Intent:** The corpus is the only thing in this system a competitor cannot buy. Every model we use is a commodity. Effort spent here compounds; effort spent tuning retrieval on a bad corpus does not.

## Measured facts — do not re-estimate

From the archives in `data/`, measured 28 Aug 2026:

- **4,710 PDFs**, 1,857 MB, across federal + Punjab + Sindh + KP + Balochistan
- **243 MB** of extracted text; **113,158** top-level sections; ~362k tree nodes
- **~96% already carry a clean text layer** — OCR is a ~150-document fallback lane, not a pillar
- Legal text compresses **4.17×** under gzip
- Federal corpus has **1,030 paths but 982 unique SHA-256** — ~48 acts share a PDF with another act. Dedupe by hash, then reconcile by hand; do not silently collapse.

## Pipeline — seven stages, each idempotent and resumable

`fetch → extract → normalise → segment → enrich → version → index`, then **QA gates**, then publish.

- **Extract with PyMuPDF, not `pdftotext`.** Coordinates are needed to detect footnote zones and indent depth.
- **Normalise** strips page furniture by *positional recurrence*, not regex — formats differ per province. Fix `__` → em-dash. Recover Urdu glyph runs lost in layout extraction. NFC.
- **Segment** on numbering grammar + indentation + font weight. Pakistani numbering includes `302`, `337A`, `337Z`, `365 A` (with a space), `184(3)`, roman chapters, and schedules with their own numbering.
- **Enrich** binds footnote markers *positionally* — they are glued to adjacent characters (`2[:]`). Parse `Ins./Subs./Om. by …` into amendment events. **Always retain `raw_note` unparsed** so a better grammar can reprocess without re-reading PDFs.
- **Publish is one transaction per instrument**, all-or-nothing, everything written unpublished until the final statement.

## The seven QA gates

Coverage ≥98% · sequence monotonic · **TOC reconciliation** · cross-reference resolution ≥95% · amendment resolution · duplicate detection · human spot-check. Nothing reaches the live index without passing all seven.

**TOC reconciliation is the highest-yield gate.** Most Pakistan Code PDFs carry a full table of contents — parse it independently and diff against the parsed body. It catches the majority of segmentation errors for free.

## The curation loop is part of the pipeline

Automated segmentation of 4,700 heterogeneous PDFs lands near 90%. The remaining ~470 documents reach the corpus through a human with the failing gate named and the source page attached. Building that console in phase 1 rather than phase 5 is the difference between 99% and demo-grade.

## Legal linkage — edge type carries meaning

Fourteen typed edges. Two matter most:

- **`notwithstanding` vs `subject_to`** point at the same provision and mean **opposite** things. Flattened into an untyped cross-reference, the answer to a statutory conflict is lost.
- **`empowers`** — an Act says "as prescribed"; the prescription lives in Rules or an SRO amended a dozen times since. Retrieving the Act alone returns a confidently incomplete answer.

**Two edges cannot be extracted from statute text at all:** `invalidated_by` lives in a judgment, `commences` lives in a gazette notification. Until those pipelines land, flag coverage as incomplete in the UI — never hide it.

## Classify on nine facets, never one tree

subject_matter · instrument_type · jurisdiction · competence · doctrinal_role · legal_origin · life_stage · citizen_situation · forum. No axis predicts another. Three of them also apply at *provision* level.

## Verify online before you claim

- **Court and gazette site structure** changes. Confirm before writing or debugging a scraper; delegate to `legal-source-scout`.
- **Whether an Act is still in force.** Never assert repeal, commencement or repugnancy status from training data.
- **Copyright line:** official court text and government-published statutes only. PLD/SCMR/YLR *headnotes and editorial matter* are third-party copyright — reporter references may be stored as identifiers, never their prose.

## Common failures

- Treating OCR as the main path. It is 4% of the corpus.
- Chunk text stored separately — duplicates the whole corpus for nothing. Chunks store **offsets**.
- Guessing an amendment's effective date when the amending instrument is not in the corpus. Flag it unresolved; never guess a version boundary.
- Serving a repealed provision as operative. That is the worst failure available to this product.
