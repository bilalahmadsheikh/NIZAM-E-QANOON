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
| **C9** | A partial, same-text or non-authoritative copy is never published beside its canonical | partial copies (0054), same-text copies (0062) and non-authoritative files (0065: an unofficial translation, or a Bill whose enacted text is held) with an active instrument whose `duplicate_of` does not point at an active instrument of the canonical (authoritative) document; active duplicates pointing at another duplicate (chain tripwire, every route) | 0, 0, 0 and 0; copies with no complete copy reported |

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
| **A7** | **The as-at query returns the corpus** | versions where `validity @> current_date`, over instruments that no active manifest declares historical (0064); historical versions are reported and judged by A13 | = all current versions |
| **A8** | OCR is distinguishable from clean text | E4 blocks with a null confidence | 0 |
| **A9** | Every parsed contents entry retains its exact source block and physical PDF page | missing or cross-document/page anchors | 0 |
| **A12** | An instrument has no year only on the owner's word | active instruments with `year` NULL and no active manifest whose evidence cites the owner's `'undated'` answer (0063); the undated count is reported | 0 without the answer; count reported, never a threshold |
| **A14** | A repealed status is a statutory repeal the corpus prints, and every one is reflected | (a) standing repeals (0066 `v_statutory_repeal_current`) not reflected on their active canonical instrument -- dated: status `repealed`, that `repealed_on`, that `repealed_by_id`; undated: `repealed_by_id` only, status `unknown` (ck_repeal); (b) active instruments `repealed` or carrying `repealed_by_id` with no standing repeal. Repealed and dated counts are reported | 0 / 0; counts reported, never a threshold |
| **A16** | The serving snapshot `operative_provision` reads matches the live derivation | `mv_instrument_serving` (0094) compared both ways with `v_instrument_currency` over released canonical laws (as-made twins excluded): currency, reason, cut-off date, territorial reach, status and (0095) territory exits; and (0096) `mv_provision_text_known_from` holds exactly the active provisions of the served laws. A difference means `tools/refresh_serving.py` was not run after a change | 0 differ; count reported |
| **A19** | The boundary evidence every active expression manifest cites is held | Every `candidate_id` an active `instrument_expression_manifest` names exists in `segmentation_boundary_candidate` (0106). The 11 Nov prune deleted 226 such rows with the revisions they were keyed to; they were restored from its archive records (D-071). The number of citations is reported | 0 missing; count reported |
| **A20** | Retrieval chunks are exactly the release, covering each version in order | (a) chunks whose version is not in `v_release_provision_version` (a replay retired it); (b) released versions with text and no chunk; (c) a version whose chunks do not run seq 0..n-1, overlap, leave anything but whitespace between or around them; (d) more than one `chunker` in the table, which would mean two splitting rules in one index. Migration 0108, D-095; post-replay step 4c keeps it. Chunks and versions are reported | 0 / 0 / 0; one chunker |
| **A21** | One embedding space in `chunk.embedding`: every chunk embedded by the active CPU generation (or none without one), in its own scope | (a) at most one active `embedding_generation` with storage `chunk.embedding` (0109; one per encoder device since 0112, D-099); (b) while one is active, chunks with no vector; with none active, chunks holding one; (c) an active generation whose `chunker` is not the table's, meaning vectors made from another splitting rule; (d) `chunk.jurisdiction` (0110) not equal to `subltree(path, 0, 1)` of the chunk's provision. A query encoded by another model would compare two spaces (docs/03 §3). D-098; the chunk worker embeds a replay's new chunks in the same transaction (post-replay step 4c). Vector count and model are reported | ≤ 1 active; 0 / 0 / 0; count reported |
| **A22** | One embedding space in `chunk_embedding_gpu`: every chunk embedded once by the active GPU generation (or the table empty without one), at its width, in its own scope | (a) at most one active GPU generation (storage `chunk_embedding_gpu`, 0112); (b) while one is active, chunks with no vector of it; (c) vectors of any other generation, or any vector with none active; (d) the active generation's recorded `dims` not the `bits` column's width (0113: `bit(4096)`); (e) its `chunker` not the table's; (f) a vector's `jurisdiction` not its chunk's (set by trigger). The GPU encoder cannot run on the corpus host, so a replay's new chunks fail (b) until topped up on Kaggle (`tools/embed_topup.py`, `tools/load_embeddings_gpu.py --topup`): a gap is never silent. D-099. Vector count and model are reported | ≤ 1 active; 0 / 0 / 0 / 0 / 0; count reported |
| **A24** | Court and authority records rest on words printed in a released law (0118, D-116, 22 Nov) | A standing `court`, `court_superintendence`, `court_jurisdiction` or `authority_rule` row whose `source_quote` is not printed (whitespace folded) in a released version of the unit it names: (source observation, expression ordinal, unit label), read through `v_court_record_source`. A replay that changes those words fails here. The record count is reported | 0 not found; count reported |
| **A25** | Every judgment file is read; every parsed reading is one released judgment with a body (0119, D-118, D-123, 22 Nov) | (a) archive members (`judgment_source`) with no active `judgment_document`; (b) an active parsed reading without exactly one active judgment; (c) an active judgment whose reading is not active and parsed; (d) a released judgment with no body paragraph, or decided after today; (e) an undated judgment (0122, D-124, 23 Nov) whose latest-possible day is not the archive's first observation of its file, or with a link that claims a version. Held, OCR-waiting and duplicate readings carry their reason by constraint. The released and undated counts are reported | 0 / 0 / 0 / 0 / 0; counts reported |
| **A26** | Judgment links are exactly the release under one linker (0119, 0121, D-119) | (a) released judgments with no `judgment_link_state`; (b) statute or case reference rows of a judgment outside the release; (c) a resolved statute reference pointing at a provision outside `v_release_provision`; (d) more than one linker. Resolved and total citations are reported | 0 / 0 / 0; one linker |
| **A27** | Judgment chunks are exactly the released body and footnote paragraphs, in the active CPU generation (0120, D-121) | (a) chunks of a judgment not released; (b) a released body or footnote paragraph with text and no chunk; (c) a chunk without a vector of the active `chunk.embedding` generation; (d) more than one chunker. The chunk count is reported | 0 / 0 / 0; one chunker |
| **A28** | The case records are exactly the release under one builder (0123, D-125) | (a) a released judgment with no `judgment_case_state` row; (b) a state, membership or relation row (either end) of a judgment not released; (c) a judgment placed in a case without a lead row, a lead row for one not placed, or a case no judgment decides; (d) a relation whose judgment or other judgment is not in its case, a dated reasons statement naming a short order after its own date, a copy of a copy, or a copy between two dated decisions of different days; (e) a case citation naming a case not held; (f) more than one builder. Cases, judgments not placed, header readings that differ, reasons statements, copies and resolved case citations are reported | 0 / 0 / 0 / 0 / 0; one builder |
| **A17** | Where a law runs is read from its own text, consistently | A standing territorial repeal (0095) removes a **federal-text** law from the repealing law's own province, or from ICT for a federal repealer; a standing `territorial_extent` assertion sits only on a federal-text law. Counts of extent clauses and territorial repeals are reported | 0 inconsistent; counts reported |
| **A18** | A partial repeal, or a unit a whole repeal excepts, is a unit the repealing law names, and it is served as one | (a) standing `provision_repeal` rows (0102) and `provision_survival` rows (0103) that do not resolve to exactly one held provision of the active repealed law; (b) a territory on a row that is not a province's law repealing part of a federal-text law for that province, or a cross-jurisdiction row with no territory; (c) `mv_provision_repeal` compared both ways with the live derivation. Repealed units and laws are reported | 0 / 0 / 0; counts reported |
| **A15** | Instrument names, numbers, dates, language and in-force status are recorded evidence, and every one is reflected | (a) standing metadata assertions (0070 `v_instrument_metadata_current`) not reflected on their active canonical instrument -- `display_title`, `text_language`, `enacted_on`, `commenced_on` equal to the value; `number` written (fill-only: a segmenter number is kept, except where a `printed_number_corrects_stored` assertion replaces a body-cited number, which must then be the number); `long_title` (0083) equal to the value; `status` `in_force` or `lapsed` (0082, 0085) unless a repeal now links the instrument; (b) active canonical instruments carrying `display_title`, `text_language`, `enacted_on`, `commenced_on`, `long_title` or status `in_force`/`lapsed` with no standing assertion. Standing counts per field are reported | 0 / 0; counts reported, never a threshold |
| **A13** | A historical text is bounded, closed, owned and points at current law | (a) bounded versions (`NOT upper_inf`) of active instruments no active manifest declares historical; (b) versions of a historical instrument outside its window; (c) active historical windows with `upper > current_date`; (d) historical manifests whose current-expression key does not resolve to exactly one active, released, non-historical instrument whose earliest version opens at or after the window's end; (e) overlapping windows of one work (same current expression). The number of historical instruments is reported | 0 / 0 / 0 / 0 / 0; count reported, never a threshold |

A7 exists because it failed. Every version was written with a validity opening
one day in the future — Python in WSL (UTC+5) against Postgres in UTC — so
INV-5's central query matched nothing while every other check passed. A corpus
that is complete, accurate and unqueryable is not a corpus.

A13 exists because A7 had to narrow (migration 0064, owner decision
decision-review-2026-10-12-k.json document 4434 q3 `historical-expression`).
Document 4434's expression 0 is the Constitution as amended to the
Twenty-second Amendment Act, 2016; it is released as a dated historical text
whose versions are written `daterange(from, to, '[)')` and so are deliberately
never `@> current_date`. A7 therefore judges only current text, and reports how
many versions it set aside. A13 is what keeps that exemption from becoming a
hole: a bounded version is admitted only under an owner-declared window that
has closed, lies wholly inside it, and names a current expression of the same
work that is itself released current law. The deferred triggers of 0064 enforce
the window and its retention at commit; A13 re-proves the rule over the stored
corpus and adds the checks no trigger can make (today's date, the release view,
overlap between expressions of one work, which has no key to constrain on).

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

*As built, 29 Oct 2026 (`nizam.verify_ocr/5`).* A Q1 review is resolved only by
recorded evidence, never by a lower threshold. Two kinds exist, both
`source_content_confirmed` assertions on the document's blob: `ocr-table-document`
answers a low legal-token rate (migration 0029), and `ocr-page-read-document`
answers an OCR confidence below 0.70 — document 02 §4's "human review below
threshold". The second is valid only when it names a render digest for every
page, and is made only after every page was read and the provisions carry that
reading (a page-by-page transcription or line-by-line check recorded as curation
patches). The verifier stores the assertion id in its result
(`page_read_assertion_id`), so every such pass is traceable to its review.

*30 Oct 2026 (`nizam.verify_ocr/6`), corrected-reading case.* An independently
page-reviewed curation can replace garbled OCR while the immutable raw blocks
still fail the legal-token check. An `ocr-page-read-document` assertion with
method `source-page-read-current-provisions/1`, the exact document id, every
page's render digest, and `reviewed_provisions_sha256` binds that review to the
current canonical provision identities, parentage, headings and text. Only an
E4 document with a matching, nonempty current tree is scored instead of the raw reading, at the
unchanged legal-token threshold of 0.25. A stale hash, missing pages or another
document cannot use this path. Legacy assertions keep their prior scope; yield
checks and raw OCR blocks remain unchanged. Mixed E3 output cannot substitute
its clean-text pages for its separate OCR-page score. The verification stores both raw
and curated legal-token rates and the bound reading hash. This is a scored
corrected reading, not a table-vocabulary exemption or an automatic pass from
the existence of a page review.

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

`./nz audit` prints all 44 criteria (A21 added 19 Nov, D-098; A22 20 Nov, D-099) including A1, A2 and A6, which it cannot
compute: A1 and A2 need an independent extractor, and A6 is enforced by an
`EXCLUDE` constraint rather than measured. They appear in the table anyway, with
where their answer comes from. A table that silently omits what it cannot check
is the failure mode this whole document exists to prevent.

## What the corpus currently says

Measured 17 Nov 2026 over 10,188 active documents and 270,129,040 extracted
characters. The release views remain the only application-safe boundary, and
every active law except 147 linked duplicates is inside it.

| Area | Result |
|---|---|
| acquisition | 10,394 observations over 10,188 distinct blobs; 66 declared acquisition exceptions with dated evidence (C1) |
| extraction lanes | 8,212 born-digital (E2), 171 mixed (E3), 1,805 OCR (E4) |
| document release scope | 134,982 released pages |
| contents agreement | 3,881 non-duplicate laws with a compared contents list: median 1.0000, mean 0.9974; 3,799 exact |
| legal release scope | 10,339 instruments and 1,172,566 provisions; 0 held |
| currency (served directly) | 8,243 current, 1,369 not current, 676 historical |
| serving snapshot | `mv_instrument_serving` 10,288 laws, `mv_provision_text_known_from` 1,156,469 provisions; A16 fresh |
| territory | extent clauses read and 48 territorial repeals recorded (18 Nov, D-078); A17 0 inconsistent |
| partial repeals | 34 repealed units in 12 laws (sections, sub-sections, clauses, Articles), 16 units in 2 laws a whole repeal excepts; A18 0 unresolved |
| boundary evidence | 315 citations by active expression manifests, 0 missing (A19, 18 Nov) |
| retrieval index | 1,132,245 chunks (A20), each with a bge-m3 sign-bit vector of the CPU generation (A21, 19 Nov) and a Qwen3-Embedding-8B `bit(4096)` vector of the GPU generation (A22, 20 Nov) |
| corpus audit | **44/44 pass** (20 Nov) |

`review`, `pending` and `unverifiable` remain evidence states, not euphemisms
for pass; a law in one of them is not released. The current state, and what to
run before any mutation, is `docs/CORPUS-STATE-2026-11-17.md`.

How the release boundary was built: migration 0030 gives document consumers a fail-closed contract through
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

Q1 implementation note,4November2026 (9851 tariff): the existing
`ocr-table-document` vocabulary exception can also explicitly opt in to
`source-page-read-current-provisions/1`. This form requires E4, every source
render, the exact current provision/tree hash and
`table_review=source_checked_article_names_and_duty_cells`. A stale tree,
another document, incomplete renders or E2/E3 cannot use it. Legacy table
assertions keep their existing semantics; the0.25 vocabulary threshold and
yield threshold are unchanged. The companion page-read assertion describes
the actual curated reading, never obsolete garbled OCR as clean table text.
Tests in `tests/test_verify_ocr.py` cover stale and incomplete table review,
other lanes and an independent low-yield failure.
