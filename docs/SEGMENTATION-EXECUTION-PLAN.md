# Production segmentation execution plan

Status: implementation contract for completing L1/L2 before retrieval. It must
be read with Documents 01–04 and 10, `CORPUS-CRITERIA.md`, `SCHEMA.md`, and
`CLEAN-REBUILD-REPORT.md`. If prose and an executable gate disagree, stop and
resolve the contract; do not weaken the gate.

## 1. Outcome and honest baseline

The output is a source-faithful, hierarchical legal corpus in which every
landed PDF byte remains immutable, every extracted character has an explicit
role, every citable node resolves to its printed page evidence, and uncertainty
is a review state rather than an invented answer.

Measured on `nizam_clean` on 10 September 2026:

| Measure | Current evidence |
|---|---:|
| effective catalogue / landed / unresolved | 4,757 / 4,716 / 41 |
| distinct active documents / pages | 4,595 / 63,047 |
| active extracted text | 128,636,469 characters; 955,153 blocks |
| expression text accounted | 135,867,627 / 135,867,627 characters |
| segmented observations | 4,668; another 48 explicitly unstructured |
| active instruments / provisions / versions | 4,788 / 512,094 / 488,518 |
| canonical active legal expressions / exact redundant trees | 4,679 / 109 |
| printed TOC evidence | 86,389 active entries, all block/page anchored |
| TOC quality | median 1.0000; 607 canonical expressions carry 1,988 promised entries unresolved (2,120 including redundant provenance trees) |
| independent quality | 4,594/4,595 pass; malformed document 4608 remains quarantined |
| fail-closed document release scope | 4,594 documents; 955,111 blocks; 0 quarantine leaks |
| citation ambiguity | 0 active sibling collisions |
| structural adjudication | 6,684 canonical-expression candidates itemized; 4,372 adjudicated; 2,312 pending in 406 observations |
| multi-instrument materialisation | 131 active source-span manifests across 11 observations; 0 S10 pending |
| fail-closed legal release scope | 3,720 instruments; 300,137 provisions; 285,156 versions; incomplete contents and S7 candidates block release |
| release audit | 29/30 pass; only S7 remains fail closed |

This proves exact accounting of landed expression text; it does not prove
universal legal accuracy. The latter cannot be claimed while S7 or 41 acquisition
items remain unresolved. Three unusual PDFs may legitimately remain
`unstructured`, but only with a recorded reason and complete block accounting.

## 2. Non-negotiable rules

1. Raw PDFs, blobs, observations, extracted blocks, OCR candidates, attempt
   ledgers, and verification evidence are append-only.
2. Byte-identical official observations remain separate until reviewed legal
   identity resolution. Similar titles, labels, or text are never sufficient
   grounds for deletion.
3. `provision` is the citation identity. Chunks are later, disposable retrieval
   projections and never appear in citations (INV-4).
4. A parser may propose structure; it may not silently correct source text,
   decide legal status, or manufacture a missing label.
5. Every accepted correction stores the exact PDF page, source block/span,
   before/after value, reason, reviewer, and parser version. It must replay
   exactly once or fail (S8).
6. Active means the current evidentiary revision, not permission to publish.
   Production reads and the default segment queue use `v_release_document` and
   its page/block companions, which contain only independently passed revisions.
7. Do not lower thresholds, replace `review` with `passed`, or use corpus means
   to hide a failing document.

## 3. Target data contract

For each official observation produce:

- one active `block_assignment_set` covering every block exactly once;
- either one active `instrument` tree or an explicit unstructured outcome and
  reason;
- typed nodes for part, chapter, section/article, subsection, clause,
  proviso, explanation, illustration, schedule, and preamble;
- verbatim label and heading, stable path, real `parent_id`, dense ordinal,
  first/last physical page, and first source block;
- provision text assembled in original reading order without deleting or
  rewriting words;
- an ordered `instrument_toc_entry` relation retaining repeated entries and
  exact source anchors;
- a complete block-role ledger: body, heading, contents, preface, preamble,
  footnote, running header, schedule row, unstructured, or unassigned;
- an exact, disposable closure of self plus real provision ancestors only;
- a `segmentation_run` manifest containing code/config/input hashes, metrics,
  decisions, patch count, outcome, and reason.

## 4. End-to-end workflow

### Phase 0 — freeze and reproduce

1. Record git state, migration status, PDF-root manifest, active row counts,
   database size, all 30 audit rows, and current queue membership.
2. Create a content-addressed dump and verify its SHA-256. Restore it under a
   temporary database name and run schema/count checks before any bulk prune.
3. Work in a new candidate database. Never rebuild over the only known-good
   candidate and never point retrieval at an unqualified corpus.
4. Pin the segmenter name, extraction/OCR configurations, runtime dependencies,
   and any model artifact hash. The same inputs must reproduce the same tree.

Exit: baseline and rollback are both independently readable.

### Phase 1 — construct risk queues from evidence

Use unioned, non-duplicating queues; one document may carry several reasons.
Persist queue reason, severity, metric values, assigned reviewer, and state.

Priority order:

1. 41 unresolved acquisitions: recover only from the named official source or
   record a dated, evidenced unavailable outcome.
2. malformed document 4608, which is declared unverifiable and remains outside
   release until a byte-distinct official copy is acquired;
3. eight TOC agreements below 0.50, then all 376 below 0.95 and all 1,988 canonical
   promised-but-unresolved printed entries;
4. 406 observations carrying 2,312 pending item-level structural decisions;
5. 48 unstructured observations (three PDFs), to confirm that table/repeal-page
   classification is legally faithful rather than parser surrender;
6. a stratified regression sample of the passing population by portal,
   jurisdiction, instrument type, century, extraction lane, script, depth,
   schedule/table presence, and document length.

Exit: every risky observation appears once in a review register with all of its
reasons; no queue is inferred from a hard-coded current count.

### Phase 2 — establish page and text ground truth

For every queued document, inspect the stored PDF page beside `text_block` and
all extraction/OCR candidates.

- Born-digital: independently compare against Poppler and page rendering;
  localize differences to page, block, and character span.
- Mixed/scanned: render at controlled DPI, run script detection, and retain OCR
  candidates. Use English and Urdu OCR where the page requires them; do not run
  English-only recognition over Urdu text. Tables may require an E5 layout
  lane.
- Ensemble selection is page-local. Prefer the candidate with source-visible
  reading order, legal-token plausibility, confidence, and agreement with other
  candidates. A model vote is evidence, not truth.
- Verify sentence order with token sequence alignment and inspect all large
  insertions, deletions, inversions, fused columns, broken ligatures, repeated
  headers, and zero-width/control characters.
- Translation may help a bilingual reviewer understand Urdu, but it never
  replaces the Urdu source string or acts as proof of wording.

Approved repairs are append-only source-verified patches to parser input. Never
mutate the original extracted/OCR candidate string.

Exit: each reviewed page is accepted or has a precise, evidenced defect and
next action; no “looks fine” outcome.

### Phase 3 — use the printed contents as an ordered structural oracle

The contents list is evidence about expected structure, not answer text and not
an unconditional body boundary.

1. Detect a contents region using heading markers, early-page position,
   typography/geometry, dot leaders, page-number columns, and a sustained run of
   legal labels. A late numeric list is not automatically a TOC.
2. Preserve each entry in printed order with label, heading, printed target
   page if present, physical source page/block, and confidence. Never store it
   first as a dictionary because repeated labels are evidence.
3. Build jurisdiction/instrument-specific label variants from the TOC, including
   `3-A`/`3A`, Urdu digits, Roman numerals, schedules, parts, and chapters. These
   variants create candidates; they do not rewrite the body.
4. Align TOC entries to body candidates with a monotonic sequence algorithm.
   Score label equality, normalized heading similarity, order, page proximity,
   hierarchy, and uniqueness. Permit explicit unmatched TOC and extra-body
   states rather than forcing a bad match.
5. Resolve the body boundary only when marker, page-position, entry-run, and
   first-body evidence agree. Otherwise retain alternatives and send to review.
6. Use unmatched entries as the segmentation worklist and coverage metric. Use
   matched headings later as high-precision retrieval aliases, but never as
   quotation or operative-law evidence.

Exit: all active contents entries retain source anchors; every match has a scored reason;
every non-match remains queryable in `v_toc_gap`.

### Phase 4 — generate structural candidates without changing text

Operate on ordered blocks plus geometry and exact character spans.

- Deterministic grammar first: instrument title/preamble, Part/Chapter,
  section/article, inserted labels (`3-A`, `3AA`), subsection, clause/subclause,
  proviso, explanation, illustration, schedule, form, and table-row patterns.
- Features vote: label grammar, punctuation, font/position, indentation,
  whitespace, neighbouring sequence, page zone, TOC expectation, and known
  jurisdiction/type conventions. Coordinates are evidence, never sole truth.
- A layout or language model may propose a node kind/boundary with a versioned
  confidence and feature trace. Deterministic constraints and the source still
  decide what may publish.
- Detect multiple instruments in one PDF before resolving repeated top-level
  labels. A repeated label can indicate a schedule/table, a second instrument,
  an OCR repetition, or a genuine nested unit; it must not be globally
  “deduplicated.”
- Parse schedules and forms as legal containers. Preserve row order and merged
  cells; do not flatten fee, limitation, offence, or stamp-duty tables into
  arbitrary paragraphs.

Exit: the candidate stream contains all plausible boundaries, their exact
evidence spans, feature scores, and explicit alternatives.

### Phase 5 — assemble a constrained legal tree

1. Apply a typed hierarchy/state machine. Reject impossible transitions, cycles,
   cross-instrument parents, non-dense ordering, and duplicate sibling citation
   identities.
2. Select the globally consistent tree with constrained dynamic programming or
   beam search over candidates. Optimize source evidence and TOC agreement,
   never node count alone.
3. Attach provisos, explanations, exceptions, definitions, and illustrations to
   the rule they qualify. Oversized schedule rows remain under their schedule.
4. Keep label and heading verbatim. Normalized forms live in separate search
   fields later.
5. Assemble text from ordered block spans and prove round-trip coverage against
   the role ledger. Apparatus remains stored and classified, not silently
   discarded.
6. Derive `provision_ancestor` recursively from `parent_id`; S9 requires exact
   self-and-real-parent closure with zero synthetic, missing, extra, or stale
   rows.

Exit: C4/C5 and S1–S6/S8/S9 pass for the candidate document before activation.

### Phase 6 — adjudicate rather than conceal ambiguity

The review interface must show rendered PDF, extracted blocks, TOC sequence,
candidate tree, alternatives, and prior revision diff together.

- Technical reviewer resolves extraction/order/layout defects.
- Pakistan legal reviewer resolves legal unit type, multi-instrument boundary,
  schedule/form meaning, identity, and any decision that changes citability.
- Require two-person review for source-text corrections and status-changing
  interpretations. Record disagreement and adjudicator.
- Use the implemented item-level S7 workflow so each of the 2,312 pending
  candidates is accepted, retyped, split, or restored with evidence.
- Store typed structural decisions separately from source-text patches. Both
  must be replayable after a full rebuild and retire-able without erasure.

Exit: S7 reaches zero pending; every change has before/after tree evidence and a
source page. If capacity prevents complete review, publish a mechanically
restricted subset rather than relabel the remainder as accurate.

### Phase 7 — validate at document, slice, and corpus level

Document gates:

- exact page count and dense reading order;
- no unaccounted block or character;
- exact label/heading/source-span fidelity for reviewed nodes;
- no orphan, cycle, cross-instrument edge, impossible path, duplicate sibling
  citation, or closure defect;
- TOC precision/recall and explicit unmatched entries;
- OCR confidence plus page-level character error and word-order evidence;
- parser warnings, automatic decisions, and corrections fully accounted.

Gold-set metrics:

- boundary precision/recall/F1 by node kind;
- exact label and heading accuracy;
- parent-edge accuracy and whole-tree exact match;
- source-span character exactness/CER and word-order error;
- TOC match precision/recall, not agreement alone;
- table cell/row order accuracy;
- results by jurisdiction, source, type, era, extraction lane, script, depth,
  and document size, with denominators and confidence intervals.

Corpus release gates are all 30 criteria plus a locked golden/challenge set,
mutation tests for the parser, deterministic rebuild hash, database self-test,
and regression diff against v5. Critical structural or citation errors cannot be
averaged away.

Exit: all gates pass. “Near perfect” is permitted only with the named metric,
denominator, sample design, and residual failures; “100%” requires exhaustive
proof for the exact property being claimed.

### Phase 8 — publish, recover, and hand off to retrieval

1. Append the qualified candidate tree and block assignment in one transaction;
   retire the predecessor only in that transaction.
2. Run `./nz test-clean`, `./nz audit-clean`, `./nz state-clean`, the locked gold
   suite, and exact corpus-diff reports.
3. Create a content-addressed dump, record SHA-256 and row counts, restore under
   a temporary database name, and repeat migrations/self-test/audit.
4. Switch consumers by configuration only after the release card is signed.
   Keep the previous database until rollback and retention policy are approved.
5. Only then start retrieval R0. Generate chunks from complete provision
   versions with ordered character spans; keep qualifiers together; use TOC
   headings only as aliases/coverage signals. Re-segmentation may regenerate
   chunks but must never invalidate provision citations or bookmarks.

## 5. Implementation state and remaining additions

Implemented through migration 0041 and segmenter `/24`:

- immutable, source-block/page-anchored S7 candidates;
- append-only structural adjudications separated from source-text patches;
- pending and legal-release views that fail closed;
- exact aggregate-to-item audit reconciliation;
- explicit `form`, `appendix`, `annexure` and `order` containers;
- dotted-label, amendment-footnote, rate/tariff and body-boundary corrections.
- letter-spaced schedule containers and Rule/Regulation-prefixed provision
  boundaries, including consecutive Rules fused into one text block;
- exact full-tree identity proofs for 109 redundant active trees without erasing
  their source observations or evidence;
- release semantics in which corrective S7 decisions remain blocked until the
  corrected tree revision exists.
- a byte-exact candidate-tree comparator and bounded heading-only replay mode;
  233 revisions were corrected only after every non-heading tree field matched;
- source-span-preserving detached-heading/body merging and guarded replay;
- an independent multi-instrument detector using prior operative structure,
  title identity, enactment/delegated-power formula and section/rule-1 reset;
- append-only boundary candidates/adjudications and an S10 release gate;
- atomic multi-expression writing, stable expression ordinals, guarded source
  spans and versioned expression manifests;
- source-reviewed materialisation of the Constitution appendices, Estacode,
  PEF sets and the other compilation documents; S10 now passes at zero pending;
- expression-aware exact duplicate resolution and archive-first pruning that
  preserves source data, manifests and identity-proof endpoints.

Before claiming segmentation complete, add or finish:

- human/legal adjudication of the remaining S7 queue and reconciliation of all
  canonical contents/body gaps;
- a versioned parser manifest containing grammar/config/model/input hashes;
- exact tree-diff tooling between active and candidate revisions;
- a locked, source-anchored segmentation gold set and mutation suite;
- TOC sequence alignment with explicit match provenance and confidence;
- table/form cell structure for E5 documents;
- an aggregate release report that separates acquisition completeness,
  extraction fidelity, text accounting, structural accuracy, and legal review.

Do not build embeddings merely to make these queues disappear. Retrieval begins
only after the corpus subset it will expose is qualified.

## 6. Reusable implementation prompt

```text
You are the senior engineer responsible for completing Nizam-e-Qanoon's legal
segmentation. Work as a PostgreSQL/data engineer, document-AI engineer, Pakistan
legal-tech reviewer, QA engineer, and production systems architect. Do not rely
on confidence or intuition where the repository, database, PDF, or official
source can provide proof.

Repository: E:\Nizam_e_Qanoon
Candidate database: nizam_clean
Immutable PDF/blob root: discover from infra configuration; verify it, never
guess it.

Read completely before changing code or data:
- CLAUDE.md and SETUP.md
- docs/01-master-architecture.html
- docs/02-corpus-and-ingestion.html, especially §§4, 5, 7, 8 and 10
- docs/03-data-and-storage.html and docs/03b-legal-data-model.html
- docs/04-retrieval.html §§4.4, 7 and 11
- docs/10-evaluation-and-quality.html
- docs/CORPUS-CRITERIA.md, docs/SCHEMA.md,
  docs/CLEAN-REBUILD-REPORT.md, and docs/SEGMENTATION-EXECUTION-PLAN.md
- current migrations, segmenter/writers/verifiers, tests, audit SQL, and the
  latest database state

Standing constraints:
1. Preserve every official observation and immutable source byte. Never delete
   or merge data because titles, labels, hashes, or text look duplicated. Only
   byte identity may deduplicate blob storage; legal identity requires review.
2. Never edit extracted text to improve a score. Retain original candidates and
   apply only source-page-verified, append-only, exactly replayable patches.
3. Every block and character must remain accounted. Uncertainty becomes an
   explicit queue/reason, not a guessed structure or silent omission.
4. Provision IDs/paths are citation identities; chunks are later disposable
   retrieval artifacts. Read active/operative views for current state.
5. Work one phase at a time to its exit condition. Before a destructive or
   corpus-wide operation, create and restore-test a content-addressed snapshot.
6. Do not lower gates, hard-code current counts as thresholds, or claim 100%
   without exhaustive evidence for the precisely named property.

Execution:
A. Capture a baseline: git status, configs, migrations, DB/relation sizes, exact
   active/historical counts, all 30 audit rows, state report, verifier evidence,
   queue membership, source manifest, and latest restore-tested dump.
B. Prove each suspected data/storage defect with SQL before fixing it. For
   derived rows, compare against canonical parent/source data. Delete only rows
   proved unreachable or regenerable and record before/after counts and bytes.
C. Build the unioned risk register in this order: 41 acquisition gaps; malformed
   document 4608; TOC <0.50, then all <0.95 and every `v_toc_gap`;
   2,312 S7 decisions/406 observations; three unstructured PDFs; stratified
   passing controls. Persist reasons without duplicating work items.
D. For each queued document compare DB text to the actual rendered PDF page.
   Use independent extraction for born-digital pages; page-local English/Urdu
   OCR ensembles and table-aware extraction where needed. Check character
   differences, sentence/token order, columns, headers, ligatures, controls,
   and bilingual script. Translation is reviewer assistance, never source proof.
E. Preserve the printed TOC as an ordered, source-anchored relation. Detect its
   zone conservatively; align entries to body candidates monotonically using
   label, heading, order, page, hierarchy, and uniqueness. Keep explicit
   unmatched states. Never collapse repeated labels or quote TOC text as law.
F. Improve segmentation with deterministic Pakistan-aware numbering grammars,
   layout/sequence evidence, a constrained hierarchy, explicit multi-instrument
   detection, and schedule/form/table structure. ML/LLM output may propose
   candidates only. Retain exact source spans and all alternatives/reasons.
G. Process the implemented item-level, source-anchored S7 queue so every pending
   decision is accepted, retyped, split, or restored. Require legal review for
   citation identity and dual review for source-text/status-changing corrections.
H. Rebuild into a separate candidate revision/database. Publish per document in
   one transaction only after its gates pass. Generate provision_ancestor from
   the real parent_id graph only.
I. Validate exact text accounting, character/word order, TOC alignment, labels,
   headings, parent edges, full-tree match, tables, path/citation uniqueness,
   patch replay, and ancestor closure. Report overall and by jurisdiction,
   source, type, era, lane, script, depth, and size. Run unit, mutation, golden,
   audit, state, self-test, snapshot-restore, and deterministic-rebuild checks.
J. Update source docs and regenerate docs/00-complete-specification.html. Report
   every changed file, migration, DB mutation, before/after count and size,
   proof artifact, remaining failure, rollback reference, and exact percentages
   with denominators. If any release gate fails, say the corpus is not release
   qualified and continue the evidenced queue; do not begin retrieval indexing.

At each phase, lead with the proven outcome, show the query/test/source evidence,
then state the next smallest phase. Stop only for a choice that materially
changes legal meaning, source retention, or production authority.
```

## 7. Authorities and method references

- Project corpus contract: Document 02 §§4–5, 7–8 and 10.
- Canonical/storage/publish contract: Document 03 §§2, 4 and 6; `SCHEMA.md`.
- TOC aliases and retrieval boundary: Document 04 §§4.4 and 7.
- Evaluation, abstention, qualification, and release evidence: Document 10.
- Official-source register for federation, provinces, territories, courts and
  regulators: Document 02 References. Official availability is time-varying and
  must be rechecked by adapters.
- LegalBench-RAG supplies a precedent for expert-labelled fine-grained legal
  retrieval evaluation; it does not validate Pakistani segmentation.
- NIST AI RMF/AI 600-1 and the ML Test Score support risk-based, versioned,
  production evaluation. They do not create Pakistani legal authority.
