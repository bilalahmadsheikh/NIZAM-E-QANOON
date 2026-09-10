# Completeness and accuracy criteria

The standard this corpus must meet, stated before it is measured. Every criterion
is a query, runs in CI, and either passes or names what failed.

The governing rule, from which the rest follows:

> **If it is in the PDF, it is in the database, and it is reachable.**
> Text is never discarded. Text that is not part of the enacted body is
> *classified*, not dropped — the contents list, a running header and an
> amendment footnote each have a home and can be queried back.

This follows [Akoma Ntoso](https://docs.oasis-open.org/legaldocml/akn-core/v1.0/akn-core-v1.0-part1-vocabulary.html),
the OASIS standard for legal documents, whose document model gives every part of
an instrument a place: a cover page, a preface, a preamble, the body, conclusions
and attachments. A parser that silently drops what it does not understand
produces a corpus nobody can audit.

---

## Completeness

| | Criterion | Measure | Threshold |
|---|---|---|---|
| **C1** | Every acquired file becomes a blob | landed hashes with no blob; blobs with no landed observation | 0 and 0 |
| **C2** | Every blob is read | blobs with no `document` | 0 |
| **C3** | Every document becomes an instrument, or records why not | documents with neither `instrument` nor a `segmentation_run` reason | 0 |
| **C4** | **Every text block is accounted for** | blocks with no row in `provision_block` | **0** |
| **C5** | **Every character is reachable** | characters in blocks whose role is `unassigned` | **0** |
| **C6** | Every provision has text, children, or a block | leaves with no version, no children, no block and no heading | 0 |
| **C7** | Failures are recorded, never silent | rejected extractions or segmentations with no `reason` | 0 |
| **C8** | Text with no structure is named, not dropped | blocks with role `unstructured`, and the documents they are in | declared and queued |

C4 and C5 are the ones that make "nothing is discarded" checkable rather than
aspirational. A block is assigned to a provision or given an explicit role; the
role `unassigned` exists so that anything the parser failed to place is visible
and countable rather than absent.

**C1 and C6 are stated the way they are because the first attempt at both was
wrong, and each wrong version failed against sound data.** C1 originally compared
two raw counts and needed a hardcoded `- 118` to balance — 4,710 landed
observations carry 4,589 distinct hashes, because the same statute published on
two portals is two correct observations of one file. C6 originally demanded a
version for every non-structural provision, which fails on the 16,341 sections
whose entire content is their subsections. A criterion that fires on correct data
trains you to ignore it.

### The roles a block may take

Derived from Akoma Ntoso's document model, narrowed to what Pakistani statutes
actually contain (measured over 952,207 blocks).

| Role | What it is | Reachable as |
|---|---|---|
| `body` | Enacted text | a `provision` |
| `contents` | The printed table of contents | the instrument's contents list |
| `preface` | Title page, gazette line, enacting formula | `instrument.long_title` / `preamble` |
| `preamble` | "WHEREAS…" | `instrument.preamble` |
| `heading` | A part, chapter or schedule heading with no text of its own | a structural `provision` |
| `footnote` | Amendment footnotes in the bottom margin | the provision on that page |
| `running_header` | "Page 90 of 179" | the page |
| `schedule_row` | A row of a schedule table | a clause of its schedule |
| `unstructured` | The document has no provision structure at all | the document and its pages; listed in `v_unstructured_document` |
| `unassigned` | The parser could not place it | **must be 0 — this is the defect counter** |

`unstructured` and `unassigned` are not synonyms, and the difference is the whole
point. `unassigned` means the document *was* segmented and the walk never reached
this block — a bug. `unstructured` means there is no provision structure to reach
it with: a PDF whose entire content is "THIS LAW HAS BEEN REPEALED", 21 pages of
recruitment rules published as a ten-column table, or a source whose text layer is
unusable. Seven documents, 729 blocks, 31,644 characters. All stored, all
reachable, each with its reason recorded.

---

## Accuracy

| | Criterion | Measure | Threshold |
|---|---|---|---|
| **A1** | Nothing lost in extraction | character recall vs an independent extractor (`pdftotext`) | every comparable document ≥ 0.999; no missing evidence |
| **A2** | Nothing fabricated | character precision, same comparison reversed | every comparable document ≥ 0.999; no missing evidence |
| **A3** | No invented provisions | provisions whose `first_block` does not exist | 0 |
| **A4** | Page anchors are real | provisions whose page lies outside the document | 0 |
| **A5** | Segmentation matches the document's own contents | ToC agreement where a contents list is printed | ≥ 0.95 median |
| **A6** | No overlapping law | overlapping `provision_version.validity` for one provision | 0, enforced by `EXCLUDE` |
| **A7** | **The as-at query returns the corpus** | versions where `validity @> current_date` | = all current versions |
| **A8** | OCR is distinguishable from clean text | E4 blocks with a null confidence | 0 |
| **A9** | Every parsed contents entry retains its exact source block and physical PDF page | missing or cross-document/page anchors | 0 |

A7 exists because it failed. Every version was written with a validity opening
one day in the future — Python in WSL (UTC+5) against Postgres in UTC — so
INV-5's central query matched nothing while every other check passed. A corpus
that is complete, accurate and unqueryable is not a corpus.

Character overlap alone is not a sufficient quality claim: it can miss scrambled
word order, a plausible-looking but wrong OCR layer, and low-confidence Urdu.
The production candidate therefore has three additional evidence gates. These
are deliberately strict: a `review` is not silently converted into a pass.

| | Criterion | Threshold |
|---|---|---|
| **Q1** | OCR quality evidence exists for every OCR-bearing document | complete; 0 unresolved reviews |
| **Q2** | Page-local word-order evidence exists for every non-E4 document | complete; 0 unresolved severe reviews |
| **Q3** | Language/text plausibility evidence exists for every document | complete; 0 unresolved reviews |

`v_document_quality_status` selects the newest append-only result from each
verifier family and reports `missing_evidence`, `review`, or `passed` per active
document. It never treats an absent verifier result as success.

---

## Structural integrity

| | Criterion | Threshold |
|---|---|---|
| **S1** | No orphan provisions (parent missing) | 0 |
| **S2** | No provision tree spanning two instruments | 0 |
| **S3** | Every `ltree` path unique | 0 duplicate paths |
| **S4** | Reading order dense and monotonic per document | 0 gaps |
| **S5** | Page rows match the extractor's reported page count | 0 mismatches |
| **S6** | No parent has two directly citable section/article children with the same kind and label | 0 ambiguous sibling citations |
| **S7** | Every automatic repeated-label decision is itemized and adjudicated | 0 pending; 0 aggregate-to-item mismatches |
| **S8** | Every approved source correction is applied exactly once in the active segmentation | 0 mismatched observations |
| **S9** | The subtree accelerator is the exact closure of real provision parentage | 0 missing, extra or stale rows |
| **S10** | Every source-evidenced internal instrument boundary is disproved or materialized as a separate expression | 0 pending boundaries |

---

## How this is run

```bash
./nz audit            # every criterion above, pass or fail with the number
./nz audit-clean      # the same audit, explicitly against nizam_clean
./nz state-clean      # completion percentages for nizam_clean
./nz verify           # A1/A2 -- the cross-extractor comparison, which no query can do
./nz verify-clean     # all four independent verifier families on nizam_clean
```

A criterion that cannot be measured is not a criterion. A threshold that has
never failed has not been tested.

The command prints every result and exits non-zero if any row is `FAIL`, so CI
cannot mistake a complete report for permission to release.

`./nz audit` prints all 30 criteria including A1, A2 and A6, which it cannot
compute: A1 and A2 need an independent extractor, and A6 is enforced by an
`EXCLUDE` constraint rather than measured. They appear in the table anyway, with
where their answer comes from. A table that silently omits what it cannot check
is the failure mode this whole document exists to prevent.

## What the clean rebuild currently says

Measured 10 Sep 2026 over 4,595 active documents and 128,636,469 extracted
characters. The whole active corpus is still a candidate; the release views are
the only application-safe boundary.

| Area | Result |
|---|---|
| acquired-PDF extraction | 4,595/4,595 distinct blobs have active documents |
| block/character accounting | 135,867,627 expression characters expected and reachable; difference 0 |
| independent quality status | 4,594/4,595 passed; document 4608 remains explicitly unverifiable |
| document release scope | 4,594 documents and 955,111 blocks; 0 quarantine leaks |
| character comparison | minimum recall 0.9991600 and minimum precision 0.9976800 under the accepted evidence policy; one declared unverifiable source |
| OCR evidence | 106/106 recorded and accepted |
| order evidence | 4,496/4,496 recorded and accepted |
| text plausibility | 4,496/4,496 recorded and accepted |
| contents agreement | median 1.0000; mean 0.9771; 2,120 gaps across all active provenance trees, 1,988 across 607 canonical release candidates |
| unambiguous sibling citations | 4,788/4,788 active expressions; 0 collisions |
| structural adjudication | 6,684 canonical-expression candidates itemized exactly; 4,372 adjudicated; 2,312 pending across 406 observations |
| exact legal-expression identity | 109 redundant active provenance trees independently fingerprinted; all source evidence retained |
| multi-instrument evidence | 131 active source-span manifests across 11 observations; independent detector and S10 queue both report 0 pending |
| legal release scope | 3,720 instruments, 300,137 provisions and 285,156 versions; unresolved printed-contents and S7 work remain excluded |
| corpus audit | 29/30 pass; only S7 remains fail closed |

The whole database therefore does **not** meet the release gate yet. `review`,
`pending` and `unverifiable` are evidence states, not euphemisms for pass.
Migration 0030 gives document consumers a fail-closed contract through
`v_release_document`, `v_release_page` and `v_release_text_block`. Migration
0035 adds immutable, source-anchored structural candidates and adjudications;
0036 makes only `accept_non_citable` release-resolving and records exact
full-tree identity proofs so redundant provenance does not duplicate legal reads;
0040 materialises each reviewed legal expression in a compilation with a
versioned source-block span, and the S10 queue is now empty;
`v_release_instrument`, `v_release_provision` and
`v_release_provision_version` also exclude every instrument with an unresolved
S7 candidate. The detailed rebuild record is in
`docs/CLEAN-REBUILD-REPORT.md`.
