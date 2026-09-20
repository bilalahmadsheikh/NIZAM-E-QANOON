# Corpus readiness — 15 September 2026

Latest read-back against `nizam_clean`: **15 September 2026, 13:37 UTC**. Later checkpoints supersede current-state counts, not historical evidence or revisions.

## Verdict

**The complete corpus is not yet release-qualified.** Base segmentation is built; **4,198 of 4,688** canonical instruments are in the fail-closed legal release views. The remaining **490** must stay withheld until their actual source/structure defects are resolved: 305 TOC-only, 155 S7-only and 30 with both. Application reads must use `v_release_instrument`, `v_release_provision`, and validity-bounded `v_release_provision_version`; active base tables are not the application corpus (docs/03 §2A and §4).

The 30-criterion audit still passes 29 criteria. S7 alone fails: **885 units in 173 observations**, with zero itemization mismatches. A5 passes its median agreement threshold but still reports **935 pending contents gaps**; passing A5 does not mean that queue is empty. No previously passing criterion regressed in the bounded replays.

## New continuation: source-backed numbering and apparatus repairs

Per docs/02 §§5.1–5.2 and docs/03 §2A, isolated editorial footnote numbers are recognized only when every numbered item independently identifies historical apparatus. Mixed operative law, unquoted modal language, ordinary numbered lists and separated `5. / A.` clauses are negative fixtures. Dotted alphabetic insertions retain their printed label; comparison keys do not merge numeric hierarchies or independent provisions.

| Source | Proven repair | Pending TOC | Pending S7 | Result |
|---|---|---:|---:|---|
| 1927, Land Preservation Act, 1900 | Split-number editorial notes had displaced the real body boundary; printed contents `5.A.` and body `5-A.` were also misread. | 23 → 0 | 2 → 0 | 24 real sections, releasable |
| 2960, Mukhtiarkars’ Courts Act, 1906 | Six historical `Subs. by…` notes below the page-4 separator had voted as sections; real opening sections were lost. | 2 → 0 | 0 → 0 | 26 real sections and three schedules, releasable |
| 3485, Punjab Public Service Commission Ordinance, 1978 | The actual oath section `4.A.` was a clause carrying a phantom label `4`; its contents prints `4-A`. | 1 → 0 | 0 → 0 | 12 real sections, releasable |
| 4495, Companies Ordinance, 1984 | Actual section `282.D` was a clause. Amendment-prefixed Fourth/Fifth/Sixth Schedule openers were not containers. Second Schedule statement forms disconnected Part III from Part II. | 1 → 0 | 1 → 0 | 538 real sections; checked schedules/forms correctly scoped; releasable |
| 4235, Forest Act, 1927 | Printed body sections `51.O/P/Q` were three clauses called `51`. Restore those actual sections and their nine child/proviso paths; preserve four already-evidenced omission dispositions. | 3 → 0 | 0 → 0 | 118 real sections; raw collisions 3 → 0; releasable |

All five were independently rendered/read, regression-tested, dry-run and replayed by **`nizam.corpus.segment/58`** (1927/2960/3485) and **`/59`** (4495/4235). All **7,832 source blocks** retain identical IDs/text, every block remains assigned, and complete persisted node fields match the reviewed dry-run trees. All predecessor trees remain retired, not deleted. The worker’s old raw collision counts (including already adjudicated candidates) are not the pending counts above. No `accept_non_citable` adjudications or release-view changes were made by this repair continuation.

Proof: [footnote repair read-back](../.review/release-zero-2026-09-15/verified-footnote-repairs.json), [oath repair read-back](../.review/release-zero-2026-09-15/verified-oath-repair.json), [Companies repair read-back](../.review/release-zero-2026-09-15/verified-companies-repair.json), [Forest repair read-back](../.review/release-zero-2026-09-15/verified-forest-repair.json), [apparatus-family probe](../.review/release-zero-2026-09-15/footnote-probe-final-reviewed.json), and [latest 30-criterion audit](../.review/release-zero-2026-09-15/audit-after-forest.txt). The `/58` parser bytes hash is `f091c175…`; final `/59` is `f1c40016…`. Universal-newline text hashes are separately identified rather than confused with exact file hashes. **246 project tests pass**, including ten immutable Forest Act blocks proving cross-page subsection continuity and correct proviso parentage. Audit/lint/drift/clustering/S7 triage were rerun after each component; six lint checks still have findings. Diagnostic S7 version reads now also enforce validity at the measurement date, not merely latest-created text.

The latest Claude continuation ran 09:07–09:39 UTC and stopped at its limit. It recorded further source readings, mostly `restore_citable`/`reparent` findings which correctly remain pending until the tree changes. Its scan-copy decision for document 4471 accounts for the additional one-instrument eligibility increase; that decision has not received an independent complete word-by-word comparison in this continuation. Artifact checks now cover **263** current canonical Claude source reviews with no file/hash/page-metadata issues; this remains integrity verification, not semantic certification.

Claude’s completed ON/OFF fingerprint covers **4,724 expression-observation targets**, not 4,724 independent documents. Nineteen documents change. Whole-family replay remains unsafe: unlinked entries increase in 244/1346 and demotions increase in 1003. These sources were **not replayed**. See [comparison](../.review/release-zero-2026-09-15/claude-fingerprint-comparison.txt) and [named remaining inventory](../.review/release-zero-2026-09-15/after-footnotes-and-claude/INVENTORY.md); that inventory precedes the final one-gap oath repair.

**4495’s newly proven schedule defects were repaired before replay.** Fourth/Fifth/Sixth Schedule containers retain their actual source labels/anchors. Statement forms are nested only when an actual Schedule Part’s printed heading corroborates them. A following Part returns to the outer Schedule only for a valid consecutive Roman sequence; genuine form-internal Part I restarts and named forms remain independent. See [137-document prefix-family probe](../.review/release-zero-2026-09-15/amended-schedule-probe-final.json), [three-document statement-family probe](../.review/release-zero-2026-09-15/form-statement-probe-final.json), and [checked ancestry](../.review/release-zero-2026-09-15/final-container-ancestry-4495.txt). Only 4495 was replayed in this container component; sources 3170/3520/4419 with additional dry-run gaps were held, not silently replayed.

These repairs qualify checked structure, not every legal assertion across the entire 376-page Companies source. Remaining cross-cutting limitations include unresolved repeal/lifecycle metadata (2960’s printed repeal tombstone and 4495’s repeal-labelled title), unvalidated placement of top-level Schedules beneath Part XVI, whole-subtree versus individual-node page ranges, and linear fee-table row associations. Fee amounts/source blocks were preserved; source preservation is not proof that every amount has the correct structured row parent.

| New continuation measurement | Before | After |
|---|---:|---:|
| Canonical instruments | 4,688 | 4,688 |
| Releasable | 4,192 | 4,198 |
| Withheld | 496 | 490 |
| Pending TOC | 965 | 935 |
| Pending S7 | 889 | 885 |
| S7 itemization mismatches | 0 | 0 |
| Database size | 2692 MB | 2702 MB |

Five newly eligible instruments follow actual parser replays; the sixth follows Claude’s separate scan-copy source decision, not an additional replay by this continuation. The [latest named remaining inventory](../.review/release-zero-2026-09-15/after-forest/INVENTORY.md) and [summary](../.review/release-zero-2026-09-15/after-forest/summary.json) name all 490 withheld expressions across 476 documents. Neither queue is zero and the entire corpus must not be described as qualified.

The Forest repair changed only three clause-to-section identities and nine descendant paths/parents; other persisted node fields match the worker dry run. Its raw S7 collisions had previously been adjudicated, so correcting them improves the actual law structure without reducing the already-zero pending S7 count for that document. Section 51.P's individual-node page end is 45 while its subsection (2) continues through page 46; a reader must use descendant spans, not assume a parent's page range covers its whole subtree.

**Held after source inspection:** 3201, Punjab Revenue Department District Cadre Ministerial Service Rules, 2011, dry-runs to three genuine rules plus its amendment-prefixed Schedule and no queue entries. Rendered pages 1–4 confirm that apparent section 4 is a Patwari table row, not a rule. However, the linear tree disconnects Tehsildar qualifications/recruitment/age cells from their row and inserts an editorial substitution note inside a continued operative sentence. Clearing its three pending S7 units before fixing those associations would qualify a known defective table; it was not replayed. Documents 2997 and 516 also remain held: dry runs respectively produce six and one raw S7 collisions. See [actual worker dry run](../.review/release-zero-2026-09-15/worker-59-dry-4235-3201.txt) and the [hash-bound rendered source manifest](../.review/release-zero-2026-09-15/after-companies/renders/manifest.json).

## Earlier Claude checkpoint — 14 September

Latest local session: `99f2b618-2d72-4b61-abf6-e395702ab6cd`, last progress message 14 September at 21:22 UTC; HEAD `ba15e0f`. The session stopped at its usage limit, not completion.

The session and fresh database drift confirm progress from the preceding checkpoint: released instruments **4,160 → 4,190**, S7 **1,046 → 890**, and contents gaps **1,005 → 966**. Claude completed the final-boundary/contents-map fix and Schedule/Part row parentage, then applied 23 bounded replays and further rendered-page S7 reviews. Those are real changes; the corpus did not become wholly ready.

Independent checks here found **247 latest source-verified Claude reviews on current canonical candidates** with existing rendered artifacts, matching stored file hashes, matching document/page filenames, and matching candidate-page metadata. This is an **artifact-integrity check**, not confirmation of 247 legal judgments or cryptographic proof that every image depicts its named PDF page. The proof tool explicitly keeps that limit in its output.

Claude's “lint clean” session wording is not a description of global corpus lint: six of nine checks still have findings. In particular, kind/title mismatches and possible conflation are still open.

## Repairs completed in this continuation

Each change follows source-aware numbering and independent contents reconciliation in **docs/02 §§5.1–5.2**, source-preserving curation in **§8.1**, and append-only revision handling in **docs/03 §2A**. Neither changes a release view or records an `accept_non_citable` decision.

| Task | Proven defect and correction | Before → after | Replay |
|---|---|---|---|
| Document 1224, Bus Stand and Traffic Control (Peshawar) Ordinance, 1975 | The title year before explicit CONTENTS was imported as a promised section. Remove that masthead year from the promise map, not from source blocks. | Pending TOC 1 → 0; 12 real sections unchanged; legal tree byte-identical in worker dry run; S7 0 → 0. Now releasable. | `/56` |
| Document 16, Sindh Civil Servants (Amendment) Ordinance, 2008 | Indented commencement “2.” occupied section 2; the real amendment was a clause and its operative sentence had been mistaken for a heading. Reparent commencement under section 1, restore operative section 2, preserve the fused marginal note separately, and reunite a wrapped enacting reference with the preamble. | Pending S7 1 → 0; 2 real sections retained; false root subsection removed from the new derived tree with its text preserved. Now releasable. | `/57` |

Document 16's current section-2 version reads exactly:

> In the Sind Civil Servants Act, 1973, section 9-A shall be omitted.

Its `marginal_note` separately retains “Omission of section 9-A Sind Act No.XIV of 1973.” This records the source amendment text, **not** a newly inferred present-day repeal status or effective date.

Evidence: document 1224 [printed title/contents](../.review/release-diagnosis-2026-09-14/renders/doc-1224-page-1.png) and [body opening](../.review/release-diagnosis-2026-09-14/renders/doc-1224-page-2.png); document 16 [complete source page](../.review/release-repair-2026-09-15/renders/doc-16-page-1.png). Source PDFs' SHA-256 values were checked against the database, both regression fixtures match immutable DB block text, and the checks were performed by assistants, not a human reviewer.

### Regression and preservation proof

- **216 project tests pass**, including six dotted-commencement cases and three title-year cases. Both parser slices received independent review before replay.
- The title-year probe inspected **1,150 candidate active documents**: four changed. Only 1224 was replayed. Documents 244/1346 move boundaries and remain held; 2475 retains other defects and was not replayed.
- The dotted-commencement probe inspected **all four candidate active documents**: only 16 changes.
- All **59 source blocks of 1224 and 10 of 16** retain identical IDs/text. PDF hashes match. Their previous instruments and **21 + 6 predecessor provisions still exist, retired**. No PDF, block, corpus row or retired revision was deleted.
- Audit, lint, drift, TOC clusters and fresh S7 triage were run after each repair. S8, C4/C5 and S9 remain passing. Lint findings are unchanged, not cleared.

The [verification artifact](../.review/release-repair-2026-09-15/verification.json) contains current/predecessor UUIDs, actual validity-bounded text, source hashes and Claude artifact checks. [Title-year family probe](../.review/release-repair-2026-09-15/title-year-probe.json) and [dotted-commencement family probe](../.review/release-repair-2026-09-15/dotted-commencement-probe.json) record before/after trees or boundary maps and parser hashes.

## Earlier 06:52 UTC checkpoint and remaining investigations

| Measure | Before this continuation | After |
|---|---:|---:|
| Canonical instruments | 4,688 | 4,688 |
| Releasable | 4,190 | 4,192 |
| Withheld | 498 | 496 |
| TOC pending | 966 | 965 |
| S7 pending | 890 | 889 |
| S7 itemization mismatches | 0 | 0 |
| Active / retired provisions | 533,587 / 489,442 | 533,586 / 489,469 |
| Database size | 2692 MB | 2692 MB |

The 496 withheld instruments split into **308 TOC-only, 156 S7-only, and 32 with both**. There are **171 TOC-only instruments with one gap** and **65 S7-only instruments with one pending unit**. These are candidates for source review, not guaranteed one-click repairs. Every remaining instrument is named in the [fresh inventory](../.review/release-repair-2026-09-15/after/INVENTORY.md), with [snapshot counts](../.review/release-repair-2026-09-15/after/summary.json).

Fresh S7 triage outside TOC-gap documents: **188 inverted, 161 nesting, 29 compendium, 307 unclear, 91 probably-correct**. These are diagnostic classifications, not decisions. There are 113 TOC signatures; nine clusters cover 44% of the gaps. Existing lookup matches do not prove that an apparent gap is recoverable body text.

Other qualification gaps remain: **9 kind/title mismatch warnings, 20 possible-conflation document warnings, 2 mixed Urdu/Arabic-codepoint blocks, and 54 placeholder/170 carriage-return title warnings**. Source classification must determine which conflation warnings are distinct laws versus apparatus or locally scoped numbering. S10's zero detector queue is not proof that those warnings are harmless.

The original weighted audit drew **200 of 4,498 automatic S7 decisions**. Its existing `E:/nizam-data/s7-audit/RESULT.md` reports only **28 rendered/read cases and one confirmed parsing error**. The full 200-case source audit remains undone; neither label survival nor artifact hashes replace it, and no corpus-wide source-audited error rate is established by that partial review.

Acquisition's **33 never-landed catalogue rows are a raw count**, not a verified unresolved queue count. This continuation did not retry acquisition or write declared-missing assertions; consult `v_acquisition_unresolved` and dated attempts before making that claim.

## Next bounded component

The fresh worklist has 170 one-gap TOC-only instruments and 64 one-unit S7-only instruments, but review is cause-driven, not queue-count-driven. **3201's Schedule table row association and apparatus binding** remain prerequisites to its replay; no independent schema convention for table cells is settled by the current documents. **3099** remains held because actual printed contents and body labels differ; recovering bare-number body labels alone would copy the wrong headings onto some rules. Reject those shortcuts, then complete the weighted 200-case S7 source audit before claiming S7 met.

### Contents-opening guard completed; 3353 not replayed

The next parser component fixes three cooperating boundary causes in **3353, Sind Agriculturists' Relief Act, 1879** (docs/02 §§5.1–5.2; docs/03 §2A). A closed bare `2A [Repealed.]` contents placeholder is retained but does not promise an operative opening. A compound first heading can be corroborated by two same-block administrative phrases only when at least three ordered operative headings corroborate the opening. The agreement guard now uses the scorer's same ambiguity-safe label reconciliation rather than comparing normalized scoring with exact spellings.

**Rejected hypothesis:** excluding the placeholder and recognizing the compound margin alone would restore the opening. The trace refuted it: the inconsistent agreement comparator still vetoed the correct page-6 boundary. Independent review additionally found and blocked a two-promise concession; the new integration negative proves that removing its three-promise guard fails. All 18 projected regression blocks exactly match their IDs/text/pages in the 373-block source artifact. They are noncontiguous excerpts, not a complete Act fixture. **250 project tests pass** at this parser checkpoint.

The corrected [316-document read-only family probe](../.review/release-zero-2026-09-15/contents-boundary-probe-reviewed.json) changes only 3353. Its [actual worker build](../.review/release-zero-2026-09-15/3353-boundary-reviewed-dry.txt) proposes **37 → 8 TOC gaps**, but **1 current pending S7 → 3 raw proposed collisions** are not comparable queue measures and do not qualify the instrument. No replay or new adjudication was performed, so the database counts and last applied `/59` checkpoint above are unchanged.

Rendered source examination identifies the remaining starts more precisely: `15B.---(1)` and `15C.---(1)` on page 15, `15D..---(1)` on page 16, `22A---(1)` on pages 18–19, `44.---(1)` on page 25, `61.---(1)` on page 32, `63A.---(1)` on page 33, and ordinary `65.` after a wrapped cross-reference on page 34. These are not one cause: dashed starts are fused into prior text/headings, 22A omits its separator dot, and 65 is suppressed by a dotted-number anti-hierarchy guard. Editorial notes also continue at the tops of later pages. Pages 18–19 repeat operative material with wording differences; neither is discarded or certified as an exact duplicate. **3353 remains withheld** while those causes are repaired. See the [exact source trace](../.review/release-zero-2026-09-15/3353-remaining-source-trace.txt) and [hash-bound renders](../.review/release-zero-2026-09-15/after-forest/renders/manifest.json).

Rejected approaches in this continuation: globally lowering the contents peak threshold to accommodate document 1665; globally treating enacting-formula parentheses as non-provisions; blanket removal of four-digit section labels; and accepting S7 collisions merely to open the gate. Document **1665's actual PDF contents disagrees with its amendment body**, so it remains a source-backed exception investigation, not a justification for inventing sections or copying its contents headings onto operative text.
