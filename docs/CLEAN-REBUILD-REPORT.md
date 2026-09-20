# Clean corpus rebuild — final measured state

> Current checkpoint, **15 September 2026, 13:37 UTC**: **4,198/4,688** canonical instruments releasable; **490** withheld; **935 TOC gaps**, **885 S7 units in 173 observations**, **29/30 audit criteria passing**, database **2702 MB**. Installed segmenter is `/59`; reviewed bounded replays of 1927/2960/3485/4495/4235 preserve all 7,832 source blocks and predecessor trees. Claude also continued its source-reading loop; most findings still require structural repair. The service-rules table in 3201 remains held despite zero-queue dry run because page review found broken associations. The dated measurements and pruning discussion below are historical, not today's state or authorization to prune. See [current readiness and source-backed proof](CORPUS-READINESS-2026-09-15.md) and regenerate [agent context](AGENT-CONTEXT.md) with `./nz context` for fresh counts. The complete corpus remains unqualified; use only legal release views in the app.

Status date: 10 September 2026  
Database: `nizam_clean`  
Active segmenter: `nizam.corpus.segment/24`  
Schema through: migration `0041_pgcrypto_evidence_hashes.sql`

## Verdict

`nizam_clean` is a sound, source-preserving evidentiary corpus and its
fail-closed release views are suitable as the input to application retrieval.
The whole active corpus is **not** release-qualified: S7 and printed-contents
coverage still block affected expressions. Production code must read only
`v_release_instrument`, `v_release_provision` and
`v_release_provision_version`, never the active base tables.

The final 30-criterion audit passes 29 criteria. The only failing criterion is
S7: 2,312 source-anchored label decisions remain pending in 406 observations.
S10 passes with zero pending internal-instrument boundaries. All landed bytes,
pages, blocks and characters remain stored and reachable; pruning removed only
restore-tested superseded derived trees.

## Current measured state

| Measure | Result |
|---|---:|
| effective official catalogue | 4,757 items |
| landed official observations | 4,716 (99.14% of effective catalogue) |
| unresolved acquisition items | 41 |
| source-observation ledger rows | 4,763, including six historical failures later recovered |
| distinct PDF blobs / active documents | 4,595 / 4,595 |
| pages / text blocks / extracted characters | 63,047 / 955,153 / 128,636,469 |
| expression characters expected / accounted | 135,867,627 / 135,867,627 |
| segmented / explicitly unstructured observations | 4,668 / 48 |
| active instruments / provisions / versions | 4,788 / 512,094 / 488,518 |
| canonical expressions / exact redundant provenance trees | 4,679 / 109 |
| release instruments / provisions / versions | 3,720 / 300,137 / 285,156 |
| database size | 1,764,095,667 bytes (`1682 MB`) after `VACUUM (ANALYZE)` |

The 41 unresolved acquisitions consist of 29 HTTP 404s, one source that states
no English PDF is available, eight invalid/non-PDF responses and three other
retry/review cases. These are acquisition gaps, not extraction omissions. Every
one of the 4,595 landed distinct hashes has a blob and active document.

## Extraction fidelity and reachability

| Gate | Measured result |
|---|---:|
| A1 character recall | 0.9991600 minimum; zero missing; one unverifiable, zero undeclared |
| A2 character precision | 0.9976800 minimum; zero accepted documents below threshold |
| OCR evidence | 106 / 106 accepted |
| word-order evidence | 4,496 / 4,496 accepted |
| text-plausibility evidence | 4,496 / 4,496 accepted |
| unexplained blocks / characters | 0 / 0 |
| release documents | 4,594 of 4,595 |

Document 4608 remains the only quality quarantine. Its active
`decode_damage` assertion records direct visual review: page 3 renders as a
corrupt black canvas, Poppler reports missing trailer/xref, OCR yields no
blocks, and the leaked block is PDF operators rather than visible text. It is
retained for evidence and excluded from release; it is not silently passed or
discarded.

All 955,153 active blocks are assigned. The accounted expression stream is
80.81% body, 12.11% named apparatus and 0.0175% explicitly unstructured text.
There are no unassigned characters, invented provisions, invalid page anchors,
or unanchored contents entries.

## Multi-instrument materialisation

Migration 0040 and the writer now model one official observation as one or more
legal expressions. Each expression has a stable ordinal, role and immutable
source-block span. `instrument_expression_manifest` versions the reviewed
boundary evidence; `save_many()` replaces all expressions for an observation
atomically while one assignment ledger accounts for every source block.

The detector was expanded for split self-name/formula blocks, Rules and Orders,
strict numbered compilation titles, OCR-tolerant outer-title matching and
source-span-aware rescanning. A full-corpus independent rerun scanned 4,679
canonical active expressions and proposed no remaining boundary. The database
also reports zero rows in `v_boundary_adjudication_pending`; audit S10 passes.

The reviewed observations now carry 131 active manifests across 11 official
observations:

- the Punjab-hosted Constitution compilation is 43 expressions: the 1,313-node
  Constitution, 17 amendment Acts and 25 amendment/revival Orders;
- Estacode is 34 legal expressions and 2,957 provision nodes per official
  observation, not one flattened pseudo-instrument;
- its second byte-identical official observation is retained as provenance and
  its 34 trees are linked, not deleted, to the exact canonical expressions;
- the PEF publication is five body-supported Rules/Regulations; the contents-only
  Punjab Education Foundation Act title was not invented as a body instrument;
- the Finance/Tobacco, Floriculture, Provident Funds and other reviewed
  compilation boundaries are separate source-anchored expressions.

Source expansion is conservative. Editorial chapter headings, contents-only
titles, running headers and lists of cited/repealed laws are excluded. The
exceptional Estacode boundary is guarded by exact block text and SHA-256
evidence in
`infra/postgres/migrations/evidence/add-estacode-international-rules-boundary.sql`.

The federal Constitution and the Punjab portal manifestation remain separate
source manifestations. The old 2,541-node Punjab tree was not proof of a second
Constitution: it included 42 appended amending instruments. Splitting those
appendices reduced its primary tree to 1,313 nodes. No different source
manifestation is collapsed unless relative structure and text match exactly.

## Printed contents and S7

The PDF contents list is retained as ordered, source-anchored evidence and is
never quoted as operative law. It provides expected labels, headings, sequence
and page hints for parsing, coverage review and later retrieval aliases.

| Measure | Result |
|---|---:|
| observations with detected contents | 3,117 |
| median / mean agreement | 1.0000 / 0.9771 |
| exact agreement | 2,494 (80.0% of contents-bearing observations) |
| promised labels not found | 1,907 on the latest observation runs |
| active provenance-tree gaps (`v_toc_gap`) | 2,120 across 623 expressions / 607 source documents |
| canonical release-blocking gaps | 1,988 across 607 expressions / 607 source documents |
| body labels not promised by contents | 4,440 |

The two gap totals answer different questions: the state report takes the
latest run per source observation, while `v_toc_gap` operates at the canonical
legal-expression release boundary. Neither means text was dropped; each is a
specific promise/body mismatch that must be resolved before that expression is
published.

The legal-release arithmetic closes exactly. Of 4,679 canonical expressions,
425 are S7-blocked and 607 are contents-blocked, with 74 in both sets; document
4608 blocks one further expression on source quality. The union therefore
excludes 959 and releases 3,720.

S7 currently has 6,684 active canonical candidates: 4,372 have an adjudication
and 2,312 remain pending in 406 observations. Candidate itemization matches the
latest run for every active expression. The live adjudication ledger contains
4,498 retained decisions, all made by
`nizam.structural_adjudicator/1`. They are independently evidence-driven, but
not human-audited; this is an explicit governance gap, not a reason to bulk
approve the remaining queue.

## Safe compaction and recovery

The post-materialisation prune was first run against an isolated restore. That
test exposed and fixed two multi-expression safety defects in the old prune:

1. successor selection joined only by observation and multiplied one retired
   expression across every active expression; it now also requires the same
   `expression_ordinal`;
2. retired expression manifests referenced their derived tree; manifests are
   preserved and only the optional retired materialisation link is severed.

The repeated isolated test selected exactly 20 superseded trees and proved the
active/release signature unchanged. The same script then pruned those 20 trees
from live, archiving their records, run evidence and derived counts first. It
removed 5,265 provisions, 5,108 versions, 8,782 block links and related derived
rows. It did **not** delete observations, blobs, documents, pages, text blocks,
OCR, assertions, active expressions, or source manifests. Nine retired
instrument endpoints remain because identity evidence references them.

The database now contains 4,797 instrument rows (4,788 active, nine retained
identity endpoints), 528,132 provision rows (512,094 active), and 15,989 archive
manifest rows. `nizam_prune_verify` is absent; the isolated verification database
was removed after each test.

Rollback artifacts:

| Purpose | Snapshot | Bytes | SHA-256 |
|---|---|---:|---|
| pre-prune, full derived history | `/snapshots/nizam_clean-20260909T192458Z.dump` | about 197 MB | `90fcebb2d112f8a68ea6ba0e692931541297f8d5f098e7e2dee9d2fc16c8e3e7` |
| post-prune, final live state | `/snapshots/nizam_clean-20260909T224947Z.dump` | 204,509,189 | `94705eba2d797ae514fb4f84b288bbd33aaede919d045e0facddfb2b8666557f` |

Both dumps were restored under an isolated database name. The final restored
signature exactly matched live: 4,763 observations, 4,595 active documents,
4,788 active instruments, 512,094 active provisions, 3,720 release instruments,
300,137 release provisions, 285,156 release versions, 2,312 pending S7 items and
zero pending S10 boundaries. Temporary databases were removed.

## Verification performed

```bash
./nz test
./nz audit
./nz state
bash tools/verify_snapshot.sh /snapshots/nizam_clean-20260909T224947Z.dump
bash tools/test_prune_retired.sh /snapshots/nizam_clean-20260909T192458Z.dump <sha256>
uv run python tools/detect_multi_instrument.py --summary-only
```

Results: 119 Python tests passed; 33 environment/database self-tests passed;
29 of 30 corpus criteria passed; S8 patch replay and S9 ancestor closure are
exact; the independent S10 detector and persisted queue are both zero. The
audit intentionally exits nonzero because S7 remains fail-closed.

## Original failure register — current disposition

| Original issue | Current disposition |
|---|---|
| TOC gaps: 2,125 / 623 | Improved but open: 2,120 provenance-inclusive gaps; the canonical release blocker is 1,988 gaps across 607 expressions |
| S7: 2,317 / 405 | Open: 2,312 / 406 after 142 source-evidenced adjudications and expression rematerialisation |
| S10 multi-Act documents | Fixed: reviewed expressions materialised; independent detector and persisted queue both zero |
| constitutional amendments unreachable | Fixed structurally: 42 appended Acts/Orders are independently addressable |
| Constitution duplicated inconsistently | Diagnosed and corrected: appended laws split from primary; distinct official manifestations preserved |
| Estacode flattened | Fixed: 34 source-spanned legal expressions; administrative apparatus remains reachable but non-operative |
| document 4608 | Declared quality quarantine; retained, not released |
| 47 never-landed ledger rows | Six recovered; 41 current acquisition gaps remain |
| machine-only adjudications | Open governance gap: 4,498 retained live-ledger decisions, one machine decider; pruned historical evidence is archived |
| retired-revision bloat | Fixed operationally: archive-first prune repeated after multi-expression safety proof |
| `nizam_prune_verify` | Fixed: temporary verifier removed; only `nizam_clean` is the application database |

## Next step

Retrieval segmentation can now begin **only for the release views**. It should
derive disposable chunks from `v_release_provision_version`, retain provision,
instrument, source-page and source-block identity, keep qualifiers with the
rule they qualify, and use contents headings as aliases/coverage signals rather
than answer text. It must not index blocked active-base-table rows.

In parallel, corpus curation must continue on the two release blockers:

1. adjudicate the remaining 2,312 S7 candidates with page evidence and human
   legal review for citation-identity decisions;
2. reconcile the 1,988 canonical TOC/body gaps without fabricating body text.

The 41 acquisition gaps and document 4608 are coverage exceptions to expose in
release metadata. A full-corpus production verdict requires those policies and
the S7/TOC queues to be resolved; the current 3,720-expression release subset is
the only qualified input to the app.

## Governing references

- Corpus and provenance contract: `docs/02-corpus-and-ingestion.html`.
- Storage, append-only publish and release views: `docs/03-data-and-storage.html`.
- Legal identity and citable-unit model: `docs/03b-legal-data-model.html`.
- Retrieval boundary and TOC aliasing: `docs/04-retrieval.html`.
- Measured quality/release method: `docs/10-evaluation-and-quality.html` and
  `docs/CORPUS-CRITERIA.md`.
- Live schema semantics: `docs/SCHEMA.md` and generated
  `docs/AGENT-CONTEXT.md`.

## L2 closeout checkpoint — 2026-09-10 17:28 UTC

This checkpoint supersedes the earlier measured counts above; historical
figures remain in this report so the improvement path is auditable. The current
state is generated from `nizam_clean` in `docs/AGENT-CONTEXT.md`.

The latest local Claude session was reviewed before this work continued. Its
diagnostic correctly identified marginal-note/body inversions as a major S7
cause and added `tools/s7_triage.py`; it did not write adjudications or change
the database. Its central warning governs the remaining work: accepting a
collision does not restore a provision that the parser typed as non-citable, so
parser repair and bounded replay take precedence over bulk adjudication.

### Changes completed in this checkpoint

- Segmenter `nizam.corpus.segment/38` is the current writer identity.
- Fused source-history notes and punctuation-separated amendment footnotes are
  retained as apparatus instead of being promoted to sections.
- Blocks containing only superscript note markers such as `6.\n7:` are retained
  as footnotes rather than parsed as decimal provisions.
- A numbered contents entry whose heading begins on the next line with `FORM`,
  `SCHEDULE` or another division word keeps that word as its heading. This
  repaired the source-faithful 18-entry contents ledger for observation 2517.
- A source-labelled `TABLE` now owns its numbered rows until a next-in-order TOC
  label and heading prove that operative sections have resumed. The rows stay
  reachable as non-citable children; no text is discarded.
- `tools/inspect_segment.py --toc-summary` now reports both the printed TOC
  source page/block and the matched body page/block. `--toc-debug` exposes the
  raw numbered stream and selected body boundary for fail-closed review.
- `tools/gen_context.py` now distinguishes raw provenance mismatches from the
  adjudication-aware `v_toc_gap_pending` count. Previously its canonical count
  included two source-absence decisions already removed from the pending view.

Seven observations were rendered, read and replayed append-only only after an
exact dry run showed no missing TOC entry and no new S7 candidate:

| Observation | Instrument | Pending rows closed | Rendered evidence |
|---:|---|---:|---|
| 2432 | Excise Duty on Minerals (Labour Welfare) Act, 1967 | 8 | contents p.1; body pp.2–3 |
| 2236 | Foodgrains (Licensing Control) Order, 1957 | 7 | contents p.1; body p.7 |
| 2517 | Punjab Partnership (Registration of Firms) Rules, 1932 | 6 | contents p.1; body p.4 |
| 2210 | Foodgrains (Licensing Control) Order, 1957 | 6 | contents p.1; body p.6 |
| 874 | Foreign Assets (Declaration and Repatriation) Act, 2018 | 6 | contents p.1; body pp.4–5 |
| 2062 | Punjab Tenancy Act, 1887 | 6 | contents p.7; body pp.54, 55, 57, 59 |
| 3240 | Sindh Coal Authority Act, 1993 | 7 | contents p.1; body pp.2–5 |

The seven bounded replays closed 46 pending TOC rows, from 1,657 to 1,611.
Every replay retired its prior tree and retained it as revision history; no
corpus row was deleted or pruned.

Observation 187 was dry-run but deliberately not replayed. Its current
candidate still leaves printed section 392 (`Repeal`) unmatched and creates two
structural collisions, one from a numeral inside an illustration. It requires a
dedicated parser/source review and is not counted as progress.

### Measured state

| Measure | Current result |
|---|---:|
| audit gate | 29 / 30 passing |
| only failing criterion | S7 |
| S7 pending | 2,370 units / 425 observations |
| S7 itemization mismatches | 0 |
| pending TOC rows | 1,611 / 535 documents / 535 instruments |
| live canonical instruments | 4,679 |
| release-ready instruments | 3,768 |
| live / retired provisions | 513,143 / 38,594 |
| active text blocks | 955,153 |
| database size | 1,729 MB |
| unresolved acquisition observations | 41 |

After each mutation `./nz audit-clean`, `./nz lint` and `./nz drift` were run.
A1–A9, C1–C8, Q1–Q3, S1–S6 and S8–S10 remain green. A7 is exact at
489,517/489,517; C5 accounts for all 135,867,627 expected characters; and S9
ancestor closure is exact at 1,211,047/1,211,047 with no missing, extra or stale
row. The complete Python suite passes under segmenter `/38`.

### Ordered remaining work

1. Continue TOC closure until `v_toc_gap_pending` is empty. Prefer parser fixes;
   use `absent_in_source` only after a rendered-page review records the cited
   page in the append-only adjudication ledger.
2. Repair and decide S7, then render and sample-audit 200 of the 4,498 earlier
   machine-only decisions, weighted toward large sibling groups. Report the
   measured error rate before treating S7 as met.
3. Resolve the 41 acquisition observations: retry the one local failure and
   record cause-specific declared-missing assertions for confirmed 404 and
   non-PDF outcomes.
4. Only after those L2 tasks are closed should the complete corpus move to the
   retrieval-segmentation stage. Release views remain the sole safe application
   boundary in the meantime.
