# Release-all handoff

This is the live continuation point for Codex, Claude Code, or a human reviewer.
It supersedes the counts and proposed yields in older release documents. The
older documents remain useful defect history, but they are not authorization to
apply an old instrument ID, decision, or replay list.

## Verified baseline

Measured from `nizam_clean` after the bounded opening-section follow-up on 23 September:

| Measure | Live value |
|---|---:|
| Canonical expressions | 4,687 |
| Released expressions | 4,122 |
| Blocked expressions | 565 |
| Blocked documents | 551 |
| Pending TOC rows | 1,030 |
| Pending S7 units | 739 |
| Pending boundaries | 0 |
| Audit | 32/33; only S7 open; A11 fresh/pass; C5 difference 0 |

The signed live target and released-tree baseline is:

```text
.artifacts/second-parser/release-after-1887-2026-09-23/
```

The post-restore manifest held 4,111 released trees. Verification after T2
reported `safe: true`, zero removed/changed baseline releases, and exactly
three expected additions (documents 1351, 1366, 1609). The post-T2 manifest
then verified the one expected addition of document 1846 with zero
removed/changed releases. The post-T2-repeal manifest authorized the following
bounded fixes and remains the active Surya proposal queue only. A bounded parser repair subsequently
released documents 1375 and 1768 as exact target replacements. The manifest
verified zero removed/changed baseline releases, changed still-blocked targets,
or unexpected additions. The exact before/after UUIDs are in
`.artifacts/release-batches/T2-parser-1375-1768-result-2026-09-23.json`.
Source-reviewed, character-preserving opening-section corrections then released
documents 3366 and 4256 without replaying any already-released document. The
same signed manifest verified two more exact target replacements and zero
removed/changed prior releases. Evidence, UUIDs and audit are in
`.artifacts/release-batches/opening-sections-3366-4256-result-2026-09-23.json`.
An exact source-layout correction subsequently released document 1287. It
changed one parser-input space to a line break where the official page prints
the section number in a separate column. The signed manifest again verified
zero removed/changed old releases. See
`.artifacts/release-batches/opening-section-1287-result-2026-09-23.json`.
One more source-reviewed opening-section correction released document 2155,
without replaying any previously released tree. The official page 3 is
operative law; the tempting document 1887 probe was rejected because page 1
is a printed contents page. See
`.artifacts/release-batches/opening-section-2155-result-2026-09-23.json`.
The operative page 3 of document 1887 was then separated from its printed
contents pages by an exact source-reviewed body boundary. The false page-1
proposal was never applied. The bounded replay released only 1887 and the
signed manifest found zero changes to prior releases. See
`.artifacts/release-batches/opening-boundary-1887-result-2026-09-23.json`.
The newly prepared and verified `release-after-1887-2026-09-23` manifest
fingerprints **all 4,122 currently released trees**. Use it for subsequent
legal-tree writes; do not rely on the older 4,115-tree proposal-run baseline
to protect these three newly released instruments.
Do not use `.artifacts/second-parser/current-pages` as an authorization source;
that run predates a corpus-wide replay and is intentionally stale.

## Fastest safe order

The following yield table was measured before the full replay and T2. It is
historical routing evidence, not a current authorization or current count:

| Classifier lane | Candidate expressions |
|---|---:|
| Decision-only S7 candidates, still requiring source check | 14 |
| Class-a TOC relink candidates | 43 |
| Unique-heading `found_elsewhere` candidates | 8 |
| Layout-aware and otherwise mechanisable candidate classes combined | 168 |
| Still requiring page review after those repairs | 435 |
| Of the page-review residue, blocked by one unit | 191 |

These are routing classifications, not guaranteed release yield. A fresh dry
run of the actual writers on 23 September accepted **zero** unattended actions:
the exact TOC relinker planned 0 revisions and skipped 397; the guarded
citation-preserving S7 writer found 0 eligible out of 465 pending candidates;
and the `found_elsewhere` writer emitted no proposal. Therefore none of the
14/43/8 candidates may be bulk-applied without new source evidence or a parser
repair. The 168 figure is a repair opportunity ceiling, not a ready-to-apply
batch.

Prefer current one-unit expressions because one source-backed decision or
repair can release each one. Re-derive the live worklist before selecting the
next batch; work on multi-blocker documents by shared defect signature rather
than arbitrary document number.

There is no safe bulk switch for the source-review residue. The source pages must decide
whether each promise is operative law, omitted/repealed text, apparatus, a
misread number, or a parser boundary defect. Surya is a second opinion that
prioritises and labels page regions; it never publishes by itself.

The expensive page-layout pass can run locally in the background without using
agent tokens. `tools/run_release_evidence_background.sh` selects whole
single-blocker evidence sets, runs Surya, imports the page candidates, and
creates proposals. It deliberately stops before adjudication or tree writes.
Review several completed proposals in one agent turn to reduce usage while
preserving the source-evidence gate.

The old `background-2026-09-23-b01` status file still says
`running-local-inference`, but that process exited and its manifest is stale
after the full replay. Its 39 rendered results are evidence only; do not import
them against current IDs. A post-T2 run exited `complete-no-input` because
its manifest had been prepared without `--stage --page-slices`; that status is
not a finding that no one-blocker work exists. The post-T2-repeal manifest
staged 5,757 blocker-page slices from 533 documents; document 4608 uses the
immutable full PDF because its page tree is malformed. A 20-file proposal-only
run was launched on 23 September in a WSL login shell. The first detached
attempt failed before inference because `uv` was not on PATH; the second
reached `output/run.log` and started its first of 19 files at 09:38 UTC.
`tools/run_release_evidence_background.sh` now marks a failed exit instead of
leaving a false running status. Check live `background.status`, `output/run.log`
and the process before reporting that it is still running; never mistake
proposals for released instruments.

Three further 40-page proposal batches are queued by
`tools/run_release_evidence_queue.sh` in one background process. They wait for
the active 19-page batch to finish, then run sequentially in unique input
directories, with signed-manifest verification on both sides of each inference
batch. Watch `background-queue.status` and `background-queue.log` in the same
run directory. They produce evidence and proposals only. Do not launch a
second simultaneous Surya process: both would use/recycle the same llama-server
and could race over the output. Local Surya already has two inference slots.
The first 19-file run got 18 results; document 4608's immutable PDF fails
PDFium with `Data format error`. Queue batch 001 selected it again and is
expected to stop after importing its other results. A hidden, fail-closed
`tools/resume_release_evidence_after_4608.sh` process is waiting for that exact
failure. It checks that 4608 alone is missing, waits for the original queue's
lock to clear, then runs batches 002 and 003 with `--exclude-document 4608`.
Its separate `background-queue-resume.status` and `.log` show progress. This
quarantine affects OCR inference only, not the release blocker or audit state;
4608 still requires a separately repaired source rendering.

### T2 source-reading outcome

Twenty one-gap documents were reviewed. Documents **1351, 1366, 1609** had
explicit omission markers and footnotes in the body. The exact-tree omission
overlay released all three, moving **4,111 to 4,114**, TOC **1,041 to 1,038**,
S7 unchanged at **739**. A follow-up source read established that document
**1846** prints section 3 as repealed. Its exact-tree overlay released one
more: **4,115** total, TOC **1,037**, S7 **739**. No baseline released tree was removed or changed;
both manifests verified `safe: true`. The remaining 16 are held;
most print operative law that the current parser has not represented under the
promised citation. A five-document bounded parser dry run found zero TOC
improvements, so replaying them unchanged would be wasted work. Evidence and
per-document findings are in
`.artifacts/release-batches/T2-result-2026-09-23.json` and
`.artifacts/release-batches/T2-repeal-1846-result-2026-09-23.json`.

Document 2605 remains a separate released-identity defect: two observations
point to the same official PDF but their released trees differ. The exact
duplicate resolver correctly refuses them. Do not silently de-duplicate a
released identity while the owner's no-withdrawal rule is in force; review the
source and record an explicit correction with its own before/after identity
accounting. The apparent 4,687 canonical denominator may change by one when
that duplicate is properly resolved.

### A11 refresh (23 September)

The 22 September census was stale after active tree revisions. A read-only
rerun examined 82,570 headed provisions and found **zero different-name
mislabels**; five findings are spelling/typography variants in five documents.
The same detector was recorded as census 211, then refreshed as census 212
after the two bounded parser replays, with the segmentation advisory lock
guard. After the opening-section replays, census 217 examined 82,575 headed
provisions and again found zero different-name mislabels and five variants.
The audit reports **A11 PASS**. The complete audit is
**32/33**; S7 remains the sole failure (739 pending). The detector output is
`.artifacts/release-batches/A11-post-1287-recorded-2026-09-23.json`. Any future
active-tree revision will correctly stale this census until it is rerun.

## One batch at a time

Keep a batch to at most 20 documents and complete this sequence before selecting
another batch:

1. Verify the current manifest. If verification is not `safe: true`, stop and
   create a new manifest from live state; never reinterpret a stale ID.
2. Select expressions that can all reach zero blockers in this batch. Prefer
   no-replay overlays, then one-blocker source reviews, then one shared parser
   defect. Never select by raw blocker count alone.
3. Read the rendered official page and its neighbouring context. Record exact
   observation, page, source block, render hash, what was observed, and the
   proposed resolution. A second-parser label alone is insufficient.
4. For a recurring defect, fix the general parser rule and add a regression
   fixture. Do not add document-ID exceptions.
5. Dry-run only the selected documents. Reject the batch if any expression
   loses a citable node, loses source-block accounting, gains TOC/S7/boundary
   work, refuses a source review, or fails to reach the expected zero blockers.
6. Apply only the bounded document list. Never run raw `segment --all --redo`.
   The segment worker's Postgres advisory lock prevents two simultaneous runs.
7. Reattach exact source-reviewed S7 and TOC decisions after replay, then apply
   only the decisions whose anchors still match uniquely.
8. Run only gates relevant to the change. Decision-only or exact-tree overlay:
   targeted dry run, source hash, release identity/tree comparison, blocker
   counts, and one corpus audit per completed batch; no full unit suite.
   Parser code change: focused parser fixtures and bounded target-tree diff,
   then the full unit suite once per shared parser change, not per document.
   If the active provision population changed, run the read-only A11 detector,
   inspect any different-name findings, then `./nz mislabelled-headings --record`
   before the audit. This prevents a valid old census from being reported as
   current after a replay; never weaken A11's stale-data guard. Verify the
   signed release manifest again.
9. Record old/new UUIDs, evidence files, commands, tests, and before/after
   counts in an append-only JSON release log. Only then start the next batch.

If a target changes but remains blocked, or a baseline released fingerprint
changes, the run is a failure. Do not call the changed state a new baseline.
The prior revision and the pre-batch snapshot are rollback evidence.

## Commands Claude should use

Run these inside WSL from the repository root:

```bash
# Prove that nobody changed the baseline or the target blocker signatures.
./nz second-parser verify \
  --run .artifacts/second-parser/release-after-1887-2026-09-23

# Re-derive the yield table and the next 100 routed expressions; this is read-only.
./nz psql-file tools/audit/blocked-release-worklist.sql

# Inspect and dry-run an explicitly bounded set.
./nz second-parser inspect --document DOCUMENT_ID
uv run python -m nizam.workers.segment \
  --documents DOC1,DOC2 --redo --dry-run --toc-improvements-summary

# After a reviewed bounded apply, restore exact durable decisions and measure.
./nz reattach
./nz toc-reattach
./nz mislabelled-headings --record
./nz audit
./nz state
# Run ./nz test only once when a shared parser implementation changes.
./nz second-parser verify \
  --run .artifacts/second-parser/release-after-1887-2026-09-23
```

When a completed batch legitimately changes a still-blocked target, retire the
old handoff manifest and prepare a new dated one only after all gates pass:

```bash
./nz second-parser prepare \
  --out .artifacts/second-parser/release-all-YYYY-MM-DD
./nz second-parser verify \
  --run .artifacts/second-parser/release-all-YYYY-MM-DD
```

## Non-negotiable regression gates

A batch is acceptable only when all of these hold:

- released expressions never decrease and remain at least 4,020;
- no previously released tree fingerprint changes;
- TOC pending, S7 pending, S7 itemization mismatches, and boundary pending do
  not increase;
- exact source character accounting remains balanced;
- no source-reviewed decision is silently orphaned or ambiguously reattached;
- every newly released expression has zero pending release blockers;
- parser tests pass, followed by the full suite when parser code changed.

For a corpus-wide replay, the only allowed entry point is
`./nz full-replay --apply`. It snapshots first, runs mandatory recovery in the
correct order, and refuses a falling release count or growing review queue.

## Definition of complete readiness

The release-all job is complete only when:

```text
released = canonical = 4,687 (or the newly measured canonical total)
v_toc_gap_pending = 0
v_structural_adjudication_pending = 0
v_boundary_adjudication_pending = 0
S7 itemization mismatches = 0
corpus audit = all pass
character accounting difference = 0
```

Counts may change as new canonical expressions are correctly materialised.
Therefore equality and zero queues are the invariant; 4,687 is this checkpoint,
not a permanent hard-coded target.

## Addendum, 23 September: why 52 recorded S7 judgements do not enact

*Claude Code, measured against the verified manifest (`safe: true`, 4,084).*

Of the one-unit blocked expressions, **52 carry only a `source_verified`
S7 decision** (`restore_citable` 21, `reparent` 28, `reject_candidate` 3) on 48
documents. They look like a no-reading batch: the page was already read, and
the enactment mechanism (`structural_resolutions_for` feeding
`_reviewed_structure_index`) exists. **A dry run of 20 of them released one.**

Building each tree in memory, exactly as the worker does, and reading the
parser's own `structural_reviews_refused` (`.probe_enactment.py`,
`.probe_refused.py`) gives the reasons:

| Why the decision is not enacted | Units |
|---|---|
| `reparent` whose evidence names no parent block. The loader requires `structural_overrides.source_reparent_blocks`, and a prose observation is correctly not guessed from | 25 |
| `restore_citable`: **two prints of one label are both restored**. Readings from different tree revisions each name a different print | 9 |
| `restore_citable`: **the stub guard**, where the swap would move the citation from, e.g., 1,240 to 215 characters | 8 |
| enacted (doc 3219), or released in the dry run (doc 1580) | 2 |

**None of these is a defect in the enactment mechanism. Every refusal is a
guard doing its job.** Two contradictory human readings, or a swap that would
demote the larger operative print, are exactly what must not be applied
unattended. Doc 3216 is the stub guard's reason for existing: two rules both
printed `9.115`, where the reviewer wrote "Both are operative".

**So these are a narrow re-read, not a no-read.** Each needs one fact from
the current page: which of two prints is the law; whether the large print is
apparatus that swallowed text or genuinely operative; which block is the parent.
Then a single bounded replay enacts them. Batch S1 (the 17 guard-refused plus 3
reparents) is doing exactly that. Documents 974 and 2997 were held out because
the background Surya run `b01` is reading their pages.

**Do not bulk-apply these 52.** The dry run is the proof that doing so would
change 19 trees in order to release 1.

## Addendum, 23 September: 85 released instruments publish a year as a section

*Claude Code. Found while sizing the year-as-label defect for a release fix.*

**102 active `section`/`article` provisions are labelled 1800–2099, across 96
documents, and 85 of those instruments are released.** A sample of 24 showed
every one to be a phantom:

- **a wrapped marginal-note citation**: "Amendment of section 17 of West
  Pakistan Ordinance XX of" / "1966.", where the year closing the citation lands
  at line start and opens a section (docs 533, 708, 595, 1110, 1498, 998, 201,
  1627);
- **a title line**: "1973." / "An Act to amend the Sind Service Tribunal
  Act" (docs 372, 1054, 744, 404, 1066, 64);
- **debris**: "1958. (See Section 3)", "1976.'", OCR noise.

So "section 1973 of the Sind Service Tribunal (Amendment) Act" resolves to a
title line. **This is a defect in the published release, not a release
blocker.**

`_YEAR_TITLE_LINE` exists (`segment.py` ~661) but whitelists what may FOLLOW
the year, and misses "An Act to amend", "North-West Frontier Province
Regulation", an amendment marker before the province name ("2[KHYBER
PAKHTUNKHWA]"), "(W. P. ORD NO.", and "CONTENTS". A blanket "no section
reaches 1800" is also unsafe: the Punjab Prisons Rules (doc 4474) have genuine
rules 1249 and 1250. The discriminator must be relative to the document's
own running sequence.

**How it must ship.** Correcting it changes released fingerprints, which the
regression gates forbid inside a release batch. It therefore goes through
`./nz full-replay --apply` (snapshot, mandatory recovery, and refusal of a
falling release count), and only after measurement shows that no released
instrument becomes blocked when its phantom is removed. It shares a mechanism
with the wrapped cross-reference defect ("…section" / "12."), and one parser
change is being built to cover both.

## Addendum, 23 September: a count-only gate passed a release SWAP

*Claude Code. Managed full replay `.artifacts/full-replay/20260922T232627Z`,
run to ship the wrapped-cross-reference and year-as-label parser fix.*

The wrapper failed its own gate (S7 pending +53: 725 → 778), and was right
to. But the release count it *passed* (4,087 → 4,087) hid a swap. Comparing
by durable identity (document, observation, expression), not UUID:

- **24 instruments that were released are no longer released**, among them
  **expression 1 of the Constitution (doc 4434)** and **the Customs Act (doc
  4451)**;
- **27 are newly released**: all 11 the fix predicted, 3 from batches S1/T1,
  and 13 more.

**A count-based release gate cannot see a swap. Compare released sets by
identity after any corpus-wide operation.** `.released_identity_diff.py` does
this; the signed manifest's verify cannot, because a full replay regenerates
every UUID.

### Cause: parser drift, not the fix

All the lost instruments' previous trees were built by `nizam.corpus.segment/59`
on 22 Sep. Building 12 of them in memory with the segmenter as it stood *before*
the fix (`a6f30d1d`) and *after* it (`b208b906`) gives **identical** S7 and
section counts: the fix is not involved. The collisions come from `segment.py`
changes made after 22 Sep and applied only through bounded replays of their
own documents. Every other released tree stayed on the older code, so the live
segmenter drifted ahead of the stored release, and **the next full replay was
bound to apply that drift in one step.**

What the drift does to previously clean released instruments:

- **Same-block duplicates** (1139, 1341, 2034, 2669, 4229): one text block
  splits into two units carrying one label, and they collide. A new parser bug.
- **An inversion** (1119): the contents line "10. Repeal of Sindh Ordinance X
  of 1995." (p.1) is kept as section 10, while the operative s.10 on p.3 is
  demoted out of citation.
- **Harmless extra rows** (983): a footnote now opens a candidate and is
  correctly demoted beneath the real s.1.

**Because the gate fails closed, none of this is published.** The affected
instruments were withdrawn, not served wrong.

### The lesson for every parser change

**Measuring a patch against the current segmenter is not enough.** The fix
agent correctly measured "0 S7 added" for its own patch. The harm came from the
distance between the current segmenter and the segmenter that built the
STORED trees. Before any corpus-wide replay, build the released trees with the
live segmenter and diff them against what is stored. That is the only
measurement that predicts what the replay will do.

## Standing rule from the project owner, 23 September: released is frozen

**A parser change reaches only BLOCKED instruments.** Released instruments
are not re-parsed. Every replay is a bounded replay of documents whose
instruments are currently unreleased.

Why this rule, and why it was not followed: the year-label fix also removed
phantom "section 1973"-style entries from 89 *released* instruments. Correcting
published law was judged worth a corpus-wide replay. That exposed all 4,084
released trees to parser drift (edits applied only through bounded replays
since 22 Sep), and 24 were withdrawn, the Constitution's expression 1 and the
Customs Act among them. **A known, bounded defect in released law was traded
for an unbounded regression risk, and the risk came due.**

Consequences:

- `./nz full-replay --apply` is not a release tool. It re-parses released
  trees. It now fails on any withdrawn instrument by identity and always takes
  a forced snapshot, but the rule is not to need it.
- A defect found in a RELEASED tree is corrected by a deliberate, per-document
  replay, measured against that document's stored tree and approved as a
  correction to published law. It is never a side effect of a parser change
  aimed at blocked instruments.
- A parser change must be measured on the blocked documents it targets, and
  must be shown to leave every released tree unchanged *if* that released
  document were ever re-parsed. The drift above is what an unchecked released
  tree looks like when it is finally re-parsed.
