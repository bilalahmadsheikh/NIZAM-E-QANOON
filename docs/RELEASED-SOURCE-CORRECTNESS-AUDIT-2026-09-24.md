# Source-backed correctness audit of the released corpus — 24 September 2026

## Bottom line

At the read-only database snapshot of **2026-09-23 20:16:13 UTC** (24 September in Pakistan), **4,122 active canonical instruments were released**. All 4,122 repository-recorded source PDF objects were present and SHA-256 matched their database records. That establishes source-file integrity for this check, **not structural correctness or independent provenance of the official publication**. Only **one released instrument** currently meets the stated full-instrument, source-image structural verification scope. Eight released instruments have source-confirmed defects; 2,106 have unresolved evidence; 2,007 passed the specified automated bundle but are not independently source-verified. No production row or release state was changed.

The corrected parser fixes the four known source-verified errors in **blocked** Documents 118 and 956 in a read-only dry run, and 144 focused tests pass. This does **not** validate the previously released corpus. In fact, the source review found confirmed defects in four instruments that had **no structural-screen flags and an unchanged reparse**.

## Population, provenance, and methods

The current database has **4,687 active canonical instruments**, **121 active non-canonical copies**, and **30,938 inactive historical revisions**. The released population is the 4,122 active canonical IDs returned by `v_release_instrument`, joined to active `instrument` and `document` rows in a repeatable-read, read-only transaction. Documents **118 and 956 are active but not released**, so neither is counted among the 4,122. The per-instrument manifest contains title, jurisdiction, current revision, observation and block boundaries, source object key and hashes, release status, stored tree version/assignment set, review records, screening flags, dry-run result, and evidence status. It does not collapse copies or historical revisions into the release denominator.

The schema has no single global provision-tree version ID. The manifest therefore identifies the stored tree by its immutable instrument revision, active block-assignment-set ID/segmenter/creation time, and provision count; the detailed comparison holds provision-version text and path differences. Source hashes were checked in the same audit window and reused from the completed integrity manifest for the refreshed 20:16 UTC database snapshot; the PDF objects were not hashed a second time seven minutes later.

The structural screen was generated **2026-09-23 17:49:51 UTC** for all 4,808 active instruments/597,387 nodes; the released subset in this manifest contains **435,717 stored provision nodes**. The screen's 64,922 flags are SQL heuristic leads, not adjudications. This audit joined those flags to the *current* release IDs. The corrected parser comparison is a separate read-only staging reparse with the existing curation inputs; it does not use the stored tree as ground truth. Original source PDFs and rendered pages, their extracted blocks, current provision paths/text and block roles were compared for the ten selected source cases. PDF SHA-256 matching was performed for every released instrument. The local PDF hash check does not itself establish that the external publication has not changed.

## Evidence classification

| Audit evidence status | Instruments | Meaning |
| --- | ---: | --- |
| A — `SOURCE_VERIFIED_CORRECT` | **1** | Full source-image structural review passed within the documented scope: Document 1. |
| B — `CONFIRMED_DEFECT` | **8** | The cited original PDF page(s) establish a material source/tree discrepancy. |
| C — `UNRESOLVED` | **2,106** | Flags, reparse differences/errors, or limited source review leave a question open. |
| D — `AUTOMATED_CHECKS_PASSED` | **2,007** | The automated bundle passed, but independent source verification is insufficient. |

These categories sum to **4,122** and are audit labels only; all 4,122 retain their production release status. **2,012** instruments passed the automated bundle (matching source hash, successful identical tree/S7/TOC reparse, active assignment set with no unassigned role, and no prior structural-screen flag). This number overlaps A/B source-reviewed cases and is not a count of source-correct instruments. **Ten** instruments had independent page-image review; **five** short instruments had every PDF page reviewed. Thus **4,112 had no independent page-image review at all**, and **4,121 are not certified structurally correct as complete instruments**. A source-confirmed defect on one page establishes B even if the rest of that instrument was not reviewed.

The source sample was deliberately selected, **not random**: the lowest document ID per jurisdiction satisfying at most two pages, no screen flags and an unchanged dry-run tree (Documents 1, 3, 19, 157, 220), plus five risk-led cases (17, 120, 247, 252, 671). The five short PDFs were reviewed in full; only the implicated page was reviewed for each risk-led case. **Eight of these ten have confirmed defects**, one is verified correct for the stated full-instrument structural scope, and one remains unresolved. Because selection was purposive, **8/10 is not a corpus error-rate estimate and no sampling confidence interval is valid**. The sample undercovers long instruments, schedules, difficult scans, and many amendment formats; a stratified probability sample or exhaustive review is still needed for a defensible population estimate.

## Source-confirmed findings in released instruments

| Document | Source blocks/pages | Confirmed effect on the released tree |
| --- | --- | --- |
| **3** | 22–27, p.1 | Section 2 operative version contains marginal heading, separator and Speaker's order/signature; Section 1 block ownership is wrong. No prior screen flag; reparse unchanged. |
| **17** | 277, 279, p.2 | Enactment-history footnote is inside Section 3 operative text. |
| **19** | 299–305, p.2 | Enacted title/preamble are classified as contents and Section 1 opening as preface; the preamble is missing from the stored preamble field/tree. No prior screen flag; reparse unchanged. |
| **120** | 3500, p.2 | Printed amendment-prefixed proviso under Section 3(1) has no distinct citable node in the released tree. The corrected reparse adds the opening, but the whole instrument is not source-certified. |
| **157** | 5524–5529, p.2 | Enacted preamble is classified as contents and a page separator contaminates the Section 2 proviso text. No prior screen flag; reparse unchanged. |
| **220** | 9060, 9071, 9074–9075, pp.1–2 | Printed Section 1(2) is fused into Section 1(1), losing its separate citation; a footnote becomes a false clause under Section 2(2); page-2 preamble is misclassified. No prior screen flag; reparse unchanged. |
| **247** | 10539–10541, p.3 | Printed amendment-prefixed Section 3(3) proviso lacks a distinct citable node; the corrected dry run adds the opening. |
| **671** | 28224–28227, p.14 | Printed Section 10 proviso is absent from the released tree and its romanettes have the wrong parent. The corrected parser adds the proviso but **still** leaves those romanettes under Section 10. |

These eight instruments require a **release-status decision under the existing policy**, not automatic withdrawal. The decision list records each instrument ID, PDF hash, evidence, legal-text/citation effect and proposed review step. The full-page images and source-block identifiers are in the [source-reviewed sample](../.artifacts/released-source-audit-2026-09-24/source-reviewed-sample.json). Document 252 is a separate **unresolved replay risk**, not a confirmed stored-tree defect: its PDF page 13 and stored tree both retain independent Section 20, but both pre-fix and corrected reparses lose that section into Section 19.

## Reparse and regression assessment

The corrected staging parser was attempted for all **4,122** released instruments. It built **4,093**: **3,816** compare identical to stored tree/S7/TOC under the comparison, and **277** differ. The other **29** are unmeasured, not parser passes: one each in Documents 1351, 1366, 1609 and 1846 (stale TOC assertions), and 25 active released expressions in Document 4497's failed multi-expression observation. Of the 277 changed released trees, **254** have a patch-attributable difference from the pre-fix control; the pre-fix parser already differed from stored trees for 24 released instruments, with overlap between those sets. A separate per-instrument change ledger classifies potential citation/parent, text, membership, block-role, source-order, S7 and TOC effects. Its row-level additions/removals are best-effort source-block matches, **not** verified legal omissions or additions, especially where multiple nodes share a block.

The final parser patch has source-verified target behavior for Documents 118 and 956 and the focused suite passed **144/144**. No released S7 or TOC output changed solely because of this patch in the completed dry run. Nonetheless the **254 patch-changed released trees are not cleared for replay**: only a few printed proviso openings have been source-checked and Document 671 still has wrong child parentage. The pre-existing Document 252 replay loss and 29 failed released builds independently block an unrestricted production replay. An identical tree only means the old and corrected parsers agree by these comparison criteria; it does **not** mean the PDF agrees with either parser.

## Structural-screen worklist

Of the earlier **64,922** raw heuristic flags, **37,462** attach to **2,085 currently released instruments**. Grouping repeated-sibling flags by instrument/parent/label and other flags by instrument/category/source block leaves **13,211 review clusters**. **Four exact leads** are corroborated by the source-reviewed cases (Document 17's footnote and the missing provisos in Documents 120, 247 and 671); **13,207** remain `not_yet_reviewed`. There were **zero source-verified false positives** and **zero cluster-specific ambiguous resolutions** in this limited review—not a claim that none exist. The ten source-reviewed cases do not automatically adjudicate every unrelated flag in their instrument. The prioritization tiers put possible nested-provision loss, missing numbered provisos and footnote contamination first; contents/source-order issues next; repeated-sibling collisions last. A duplicate label by itself is neutral until the PDF establishes its actual parent and role.

| Category | Raw released flags | Released clusters | Affected released instruments |
| --- | ---: | ---: | ---: |
| Repeated sibling label | 34,582 | 10,498 | 1,511 |
| Top-level nested kind | 957 | 810 | 285 |
| Root source-order inversion | 32 | 32 | 22 |
| Numbered proviso without own node | 575 | 575 | 255 |
| Footnote phrase in operative text | 1,239 | 1,234 | 648 |
| TOC source promoted | 77 | 62 | 33 |

Four of the confirmed defective, unchanged instruments (3, 19, 157, 220) had **zero** screen flags, demonstrating why resolving every existing flag would still not prove the released corpus correct. The four confirmed cluster labels apply only to the exact reviewed leads; assigning labels in bulk without page review would overstate evidence.

## What is and is not concluded

1. **Known parser targets:** the source-verified Document 118/956 errors are corrected in proposed code and focused tests; those instruments remain blocked/unreleased. Other parser defects remain, including the released Document 671 nesting error.
2. **Regression safety:** not established for corpus replay. There are 254 patch-attributable released-tree changes, 24 pre-fix released differences, 29 released builds that failed, and a source-proven Section 20 loss on Document 252 reparse. No production replay was run.
3. **Previously released corpus:** not independently validated in full. One instrument has full-instrument structural source verification under the stated scope, eight have confirmed defects, and the remainder are either unresolved or automated-only. A hash-matched PDF and an unchanged tree cannot certify them.

Next, triage the eight release decisions without automatically withdrawing anything; fix and source-test each distinct cause; resolve the 29 build failures and the Document 252 replay loss; then source-review the 277 changed released trees and high-impact flag clusters. For unchanged trees, use a documented risk-stratified **probability** sample with full-page coverage (or exhaustive review), report error estimates with appropriate uncertainty, and expand review when defects are found. Any later production reparse or release-state change requires a separate authorized, reversible deployment and old-release identity guard.

## Machine-readable evidence

- [Instrument-by-instrument evidence](../.artifacts/released-source-audit-2026-09-24/evidence.jsonl) and [snapshot summary](../.artifacts/released-source-audit-2026-09-24/evidence.summary.json): every currently released canonical instrument, source integrity, stored/reparse/review evidence and A–D classification.
- [Released structural-flag clusters](../.artifacts/released-source-audit-2026-09-24/released-flag-clusters.jsonl) and [counts](../.artifacts/released-source-audit-2026-09-24/released-flag-clusters.summary.json): prioritized heuristic worklist mapped to current release IDs.
- [Released reparse change classification](../.artifacts/released-source-audit-2026-09-24/released-reparse-changes.jsonl) and [counts](../.artifacts/released-source-audit-2026-09-24/released-reparse-changes.summary.json): all 277 changed released instruments; full before/after node, source-block, S7 and TOC detail is in [changed-detail.jsonl](../.artifacts/structural-parser-fix-2026-09-23/changed-detail.jsonl).
- [Source-reviewed sample](../.artifacts/released-source-audit-2026-09-24/source-reviewed-sample.json) and [release-status decision list](../.artifacts/released-source-audit-2026-09-24/release-status-decisions.json).
- [Known parser fix and replay validation](STRUCTURAL-PARSER-FIX-VALIDATION-2026-09-23.md), including the source-verified Document 118 before/after and actual test result.

No production records, adjudications, published instruments or release states were modified in this audit.
