# Remaining release blockers: evidence-based diagnosis

> This is the **14 September historical snapshot**. Subsequent contents/schedule repairs and source reviews changed the database. Documents 1438/2581's final-boundary fix was completed by Claude; document 1224's remaining title-year gap and document 16's operative-section inversion were repaired on 15 September. See [current readiness](CORPUS-READINESS-2026-09-15.md) and [fresh remaining inventory](../.review/release-repair-2026-09-15/after/INVENTORY.md): 4,192 releasable, 496 withheld, 965 TOC gaps and 889 S7 units. The individual diagnoses below retain their original measured date.

Snapshot: **14 September 2026, 06:45:04 UTC**, `nizam_clean`. This is a diagnostic report, not a release certification or a corpus repair. No corpus rows, adjudications, or release views were changed during this investigation.

## Measured backlog

| Measure | Count |
|---|---:|
| Active, canonical instruments | 4,688 |
| In the release view | 4,146 |
| Outside the release view | 542 |
| Documents containing those blocked instruments | 521 |
| TOC-only blocked instruments | 330 |
| S7-only blocked instruments | 200 |
| Blocked by both | 12 |
| Pending TOC gaps | 1,005 |
| Pending S7 units | 1,035 |
| TOC-only instruments with exactly one gap | 181 |
| S7-only instruments with exactly one pending unit | 81 |

The last two rows identify **262 candidate instruments for a bounded review batch**, not 262 proven easy fixes. Clearing many units in one large book releases only one instrument; recovering one correct section can release a small instrument. Neither metric alone measures legal usefulness.

Every blocked instrument is named, with its UUID, document ID, labels and blocker counts, in the [complete inventory](../.review/release-diagnosis-2026-09-14/INVENTORY.md). [Snapshot metadata](../.review/release-diagnosis-2026-09-14/summary.json) and [instrument/source identities](../.review/release-diagnosis-2026-09-14/instruments.json) make the counts reproducible.

## Confirmed problems in specific instruments

Page references below are one-based PDF pages. Selected pages were rendered from local source PDFs after verifying the stored SHA-256. They were inspected by the assistant, **not a human reviewer**. No human-review assertion was written. These are case diagnoses, not a whole-instrument accuracy audit.

### 1. Commercial Documents Evidence Act, 1939 — documents 1438 and 2581

**Blockers: 21 and 20 TOC gaps, respectively; no pending S7.**

The printed contents has sections 1–4 and a Schedule. The body prints all four sections. The Schedule then contains its own numbered items. The stored parse has 28 section-kind nodes: sections 1–4, followed by `pt_I.s_1` through `pt_I.s_24`, with no Schedule wrapper. Those latter nodes are under Part I, not all at the instrument root.

The unresolved labels are 5–24 in both records, plus 157 in document 1438. They are run-level missing labels, **not unlinked, source-anchored TOC entries**. A fresh dry run still links all four genuine TOC entries and still reports 21/20 gaps. This proves a mismatch between the promised-label map and the actual contents-entry ledger; it is not proof that 41 pieces of legislation are missing.

Evidence: document 1438 [contents](../.review/release-diagnosis-2026-09-14/renders/doc-1438-page-1.png), [four sections](../.review/release-diagnosis-2026-09-14/renders/doc-1438-page-2.png), [Schedule/Part I](../.review/release-diagnosis-2026-09-14/renders/doc-1438-page-3.png); document 2581 [contents](../.review/release-diagnosis-2026-09-14/renders/doc-2581-page-1.png) and [body](../.review/release-diagnosis-2026-09-14/renders/doc-2581-page-2.png).

**Repair boundary:** construct both TOC representations from the same bounded source region, retain the Schedule container, and scope its numbered items correctly. Do not delete the schedule, manufacture sections 5–24, or simply filter the pending view. This is the strongest contained first fix: two records, the same source structure, 41 misleading gaps, and no pending S7 dependency. Full-tree tests remain necessary.

### 2. Sindh Control of Narcotic Substances Act, 2024 — document 3880

**Blocker: one run-level TOC gap, label 6; no pending S7.**

The [contents on page 1](../.review/release-diagnosis-2026-09-14/renders/doc-3880-page-1.png) lists section 6, and [page 12](../.review/release-diagnosis-2026-09-14/renders/doc-3880-page-12.png) visibly prints its operative prohibition. The database already has section `sindh.act.y2024_VIII_o4542.ch_II.s_6`, source block 510225, spanning pages 12–13. Its heading field contains operative text rather than the printed marginal heading.

**Repair boundary:** trace why the real section does not satisfy the promised-label/entry ledger, and correct the heading/body mapping while preserving its text and continuation. There are other number-6 items in tables/schedules, so an unscoped label match is not a safe fix. The missing-section diagnosis is disproved; the precise failing matcher branch still needs a focused trace. This is another small, concrete next investigation, not a reason to regenerate the source.

### 3. Karachi Metropolitan University Act, 2023 — document 3793

**Blockers: 11 TOC labels, 62–72; no pending S7.**

The source itself changes numbering. Its [contents, page 3](../.review/release-diagnosis-2026-09-14/renders/doc-3793-page-3.png), lists 62 Faculties, 63 Dean, 64 Teaching Department, and later entries through 72. The body finishes section 61 and starts **THE SCHEDULE / FIRST STATUTES**, where [Faculties is item 1, page 39](../.review/release-diagnosis-2026-09-14/renders/doc-3793-page-39.png), and [Dean and Teaching Department are items 2 and 3, page 41](../.review/release-diagnosis-2026-09-14/renders/doc-3793-page-41.png).

The current tree does contain a Schedule container and item 1 below it. Therefore this is not the same defect as the missing Schedule wrapper in documents 1438/2581. Some later schedule text also has mixed assigned roles, so title similarity alone is insufficient to certify all eleven links.

**Repair boundary:** verify and persist an explicit contents-to-schedule mapping, preserving both printed numberings and the schedule's legal scope. Do not relabel First Statutes item 1 as Act section 62. Check all eleven target spans and their parentage before closing the instrument.

### 4. Bus Stand and Traffic Control (Peshawar) Ordinance, 1975 — document 1224

**Blocker: one pending S7 unit, label 12.**

The kept section-12 occurrence comes from [page 1's contents](../.review/release-diagnosis-2026-09-14/renders/doc-1224-page-1.png). Its stored text includes the title/preamble. The actual rule-making provision is printed on [page 5](../.review/release-diagnosis-2026-09-14/renders/doc-1224-page-5.png), but is stored as `cl_12`, while the wrong occurrence occupies `s_12`.

**Repair boundary:** repair the contents/body transition, restore the operative occurrence as section 12, and verify all earlier sections too. The current dry run emits twelve raw collisions, whereas only one is pending after existing decisions; clearing the remaining pending row alone is not a whole-tree repair.

### 5. Balochistan Adaptation and Repeal of Laws Act, 1957 — document 2975

**Blocker: one pending S7 unit, label 7.**

The same category appears here: [page 1](../.review/release-diagnosis-2026-09-14/renders/doc-2975-page-1.png) supplies the contents occurrence of “Savings and validation,” while [page 7](../.review/release-diagnosis-2026-09-14/renders/doc-2975-page-7.png) prints the operative section 7. The latter is demoted to a clause; the kept section's text contains title/preamble material. A clause's own text being null does not mean its children contain no law.

**Repair boundary:** fix the boundary and section ownership, including subsection children. Current dry-run raw collisions are six, not the single pending item. As with 1224, recheck already-decided siblings.

### 6. Sindh Mental Health Act, 2013 — document 2800

**Blockers: 14 TOC gaps; no pending S7.**

At least two missing sections are plainly printed and extracted: section 10 on [page 13](../.review/release-diagnosis-2026-09-14/renders/doc-2800-page-13.png), and section 53 on [page 36](../.review/release-diagnosis-2026-09-14/renders/doc-2800-page-36.png). Their starts occur inside larger extracted blocks, alongside right-column marginal headings. They did not become section nodes in the stored revision.

A dry run of the inspected parser increased section-kind nodes from 45 to 58 and reduced unresolved TOC items from 14 to 3, leaving labels **2, 25, 27**, and emitted three raw collisions. These figures are before carrying forward adjudications; they are not a certified release result.

**Repair boundary:** inspect the improved full tree and its three residual labels/collisions before any bounded replay. Much is recoverable by current code, but replay alone is not yet shown to release this instrument safely.

### 7. Punjab Prisons Rules, 1978 — document 4474

**Blockers: 69 pending S7 units; no TOC gaps.**

Real Rules 14–16 are printed on [page 8](../.review/release-diagnosis-2026-09-14/renders/doc-4474-page-8.png). On [page 28](../.review/release-diagnosis-2026-09-14/renders/doc-4474-page-28.png), a property list under Rule 75 has items 14–16 for a mug/piala, plate and mug. Those item numbers are not fresh Rules 14–16.

**Repair boundary:** preserve list/table context and parent the items under the governing rule. Do not delete them or promote them to independent rule citations. This explains the inspected collisions, **not all 69**: other clusters occur on pages 29, 86, 188, 464–465 and elsewhere. The book needs separate table, form and appendix review. Resolving all 69 would release one instrument, not 69.

### 8. Sindh Councils (Conduct of Business) Rules, 2001 — document 3389

**Blocker: one pending S7 unit, label 13.**

[Page 5](../.review/release-diagnosis-2026-09-14/renders/doc-3389-page-5.png) contains Rule 15's prose, ending with a cross-reference to Rule 13. The words `Rule 13.` wrap onto a new line. The subdivision rule `_INNER_RULE` treats that line as a new rule start and creates an empty duplicate clause. The genuine Rule 13 already exists on page 4.

**Repair boundary:** require actual heading/start context rather than line-start `Rule N.` alone; keep the reference inside Rule 15's text. This source has more than one active expression, so the diagnostic tool correctly held it out of ordinary single-expression replay. Ownership must be respected in the eventual fix.

### 9. Provincial Urban Development Board (Validation of Actions) Ordinance, 1980 — document 1079

**Blocker: one TOC gap, label 1980.**

[Page 2](../.review/release-diagnosis-2026-09-14/renders/doc-1079-page-2.png) shows the year in the instrument title/number, not section 1980. The bogus entry is 509561, source block 51085. Current dry-run output retains the error.

**Repair boundary:** exclude front-matter material consistently from both the promised-label map and source-entry ledger. A global four-digit-number ban is not justified. The prior investigation documents why filtering only the ledger increased gaps instead of fixing them.

### 10. Balochistan Witness Protection Act, 2016 — document 127

**Reported blockers: 14 TOC gaps, labels 16–29; no pending S7. The number understates the problem.**

All seven PDF pages were rendered and inspected. The contents on [page 1](../.review/release-diagnosis-2026-09-14/renders/doc-127-page-1.png) and [page 2](../.review/release-diagnosis-2026-09-14/renders/doc-127-page-2.png) promises sections 1–29. After the gazette title page, [page 4](../.review/release-diagnosis-2026-09-14/renders/doc-127-page-4.png) prints sections 1–2. [Page 5](../.review/release-diagnosis-2026-09-14/renders/doc-127-page-5.png) says “See Schedule on Next Page.” [Page 6](../.review/release-diagnosis-2026-09-14/renders/doc-127-page-6.png) is the schedule's numbered offence list, and page 7 is blank.

The source body does not print sections 3–29. The stored tree has fifteen section-kind nodes, allowing schedule numbers to mask part of that absence. This is **incomplete source plus incorrect schedule scope**, not merely fourteen missing links.

**Repair boundary:** obtain a complete authoritative source and retain this one as provenance; then parse the real sections and schedule separately. Without such a source, do not certify full-text completeness or mark absent material as repealed. Assistant inspection is not permission to write `human_page_review=true`.

### 11. Sind Agriculturists' Relief Act, 1879 — document 3353

**Blockers: 37 TOC gaps and one pending S7 unit.**

The source on [page 7](../.review/release-diagnosis-2026-09-14/renders/doc-3353-page-7.png) and [page 11](../.review/release-diagnosis-2026-09-14/renders/doc-3353-page-11.png) distinguishes body sections, right-margin headings and numbered editorial footnotes. Pending TOC rows include footnote text as if it were section-heading text. The same number can therefore refer to body law or editorial apparatus.

**Repair boundary:** segregate footnotes and marginal headings using page-local geometry and legal hierarchy, then reconstruct genuine section promises. Multiple mechanisms coexist. This is a useful stress-test fixture, not a safe one-rule bulk closeout.

## What the whole-backlog search does and does not establish

The strict search deliberately preserves internal punctuation: `2.1` is not `21`, and `2-A` is not automatically `2A`. It excludes blocks assigned the contents role, but those assigned roles can themselves be wrong. A hit is therefore a lead, not a recovery verdict.

| Search signal, mutually exclusive classification | TOC units |
|---|---:|
| Matching label already in a section/article node | 201 |
| Line-start label outside assigned contents | 235 |
| Heading outside assigned contents | 295 |
| Match only outside the expression span | 2 |
| No strict match | 272 |

These add to 1,005. They **do not** establish that 733 are recoverable or 272 are absent. Document 127 illustrates why a matching section number can belong to the wrong legal object.

Additional narrow signatures identify candidate families, with overlap and false positives still possible:

| Family lead | Units | Instruments | What is actually established |
|---|---:|---:|---|
| Run-level gaps without an unlinked entry row | 42 | 3 | 1438/2581: polluted promises; 3880: real section exists but remains missing in ledger |
| Year-shaped missing labels | 19 | 18 | Title-year error visually confirmed for 1079; ten instruments have no other pending blocker in this signature |
| University schedule-like headings | 54 | 10 | Numbering mismatch confirmed for selected entries in 3793; other cases need target-page review |
| S7 kept occurrence on a page with an explicit contents marker | 86 | 23 | Candidate set only; confirmed contents/body inversions include 1224 and 2975, and this narrow signature is not exhaustive |
| Empty wrapped cross-reference candidate | 1 | 1 | Confirmed in 3389 |

See [signal membership](../.review/release-diagnosis-2026-09-14/signals.json), [TOC row evidence](../.review/release-diagnosis-2026-09-14/toc.json), and [S7 candidate/kept evidence](../.review/release-diagnosis-2026-09-14/s7.json). The 542-instrument inventory is exhaustive for the snapshot; the visual root-cause review is not.

## Which work is most valuable next?

1. **Best contained engineering start: 1438 + 2581**, using 3880 and 1079 as additional promised-map/ledger regression cases. Fix the shared upstream representation, not the release gate. This tackles concrete false gaps while retaining real schedules and text. All four instruments are TOC-only, but their fixes are not yet proved equivalent.
2. **Best correctness-risk priority: 1224 + 2975**, then the broader contents/body S7 family. The application currently risks citing contents/preamble text instead of operative law. Inspect all collisions in those documents, including already-decided ones.
3. **Best bounded mapping family: university statutes**, starting with all eleven entries in 3793, then testing the related titles in the signal inventory. Preserve both numbering systems; do not invent sections.
4. **Best batch for release-count efficiency: the 262 single-blocker instruments**, partitioned by demonstrated cause. Review one source case per proposed family before broadening a rule. Small blocker count does not imply low legal risk.
5. **Separate workstreams:** source acquisition for 127; large-table/form hierarchy for 4474; footnote/geometry handling for 3353; residual parser issues and replay validation for 2800. Mixing them into one label-shaped queue hides their different dependencies.

No exact completion date or guaranteed batch yield follows from the present evidence. A useful plan can now name fixtures, intended structural changes, safety checks and candidate families instead of budgeting one generic operation per gap.

## Corrections to earlier hypotheses and operational constraints

- “Not found in the tree” does not imply “not printed in the PDF”: 2800 disproves that inference directly.
- “The number remains citable” does not prove the right text remains citable: 1224/2975 are concrete counterexamples.
- “Every gap in a document with real contents is a real section promise” is false: 1438/2581 mix genuine contents with unrelated run-level labels.
- A repeated number is not inherently a duplicate law: Rule 75's list in 4474 must retain its own items without becoming Rules 14–16 again.
- A global geometry threshold or label-shape rule is not a substitute for source/parent context.
- [WHY-S7-AND-TOC-CANNOT-CLOSE.md](WHY-S7-AND-TOC-CANNOT-CLOSE.md) correctly warns that filtering only the TOC-entry ledger creates extra run-level gaps. Its broader historical conclusion that no independent evidence remains is not a sufficient description of these newly inspected cases. The rendered source supplies independent evidence of concrete parser defects.

Governing constraints: [AGENT-CONTEXT.md](AGENT-CONTEXT.md), active/canonical query rules and append-only corpus policy; the historical investigation above, section “A contents-parser fix that had to be reverted”; and the existing distinction between assistant and human source review. Any eventual repair must retire prior revisions, preserve source text, and run audit, lint, drift and targeted source-regression checks. Do not use an adjudication to disguise incorrect citation ownership.

## Reproducibility and limits

`tools/diagnose_release_snapshot.py` collected a PostgreSQL **repeatable-read, read-only transaction**. `tools/profile_release_snapshot.py` creates the offline family inventory. `tools/render_release_diagnosis.py` verifies PDF hashes and calls the existing source renderer. `tools/diagnose_selected_parses.py` builds candidate trees without persisting them and refuses ordinary replay simulation for multi-expression sources.

The snapshot records Git HEAD `3f3c0b0349a72585c9079a9edf8d30d7a7673a62`. The inspected dry runs record segmenter SHA-256 `66245f0bceb1577c460814e5ec6777199bb1406777a3d72fed39e8a9dd19b55d`. Other work continued in the shared worktree during diagnosis; these results should not be silently attributed to a later code version. Raw prospective collision counts and already-adjudicated pending counts are different measures and are labelled separately above.

Rendered files and source/render hashes are in the [render manifest](../.review/release-diagnosis-2026-09-14/renders/manifest.json). Rendering is not proof that every rendered page was inspected; the explicit linked case evidence and the seven-page review of document 127 state the review scope. The JSON artifacts retain source URLs and blob hashes; they are the reference for exact source identity.

No new full audit or production-readiness certification was performed in this diagnostic task. Membership in the existing release view means the current gates permit an instrument; it is not a fresh word-for-word accuracy guarantee.
