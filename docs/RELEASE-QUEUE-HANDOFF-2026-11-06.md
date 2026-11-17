# Release-queue handoff — 6 November 2026

<!-- superseded-banner -->
> **Historical record — superseded.** The counts, queues and next steps below describe the
> corpus at the date of this report and are no longer current: the release queue it
> describes has since closed. On 17 Nov 2026, 10,339 laws are released, none is held, and
> all 40 audit criteria pass. The live state and continuation point is
> [CORPUS-STATE-2026-11-17.md](CORPUS-STATE-2026-11-17.md). This file is kept unchanged as
> the record of how those decisions were made.

Written for: the next session (Claude or Codex) picking up the release queue, and the owner reviewing where it stands.
Supersedes the *live* checkpoint in `RELEASE-ALL-HANDOFF-2026-09-23.md` (that file keeps the signed 23 September
baseline of 4,687 expressions; the corpus has since grown, see §1).

The session this records is the Claude "lead" session whose transcript ended at its usage limit at 00:02 on 6 Nov, plus
the Codex sessions of 3–5 Nov that ran beside it. Its working log is
`.artifacts/release-work-2026-09-24/CLAUDE-CLAIMS.md` (3,407 lines, 140 dated entries). This document is the digest of
that log; the log remains the per-document record.

---

## 1. State, measured 6 Nov 2026 (from the database, not from the log)

| | |
|---|---|
| Canonical expressions (`is_active AND duplicate_of IS NULL`) | **8,796** |
| Released (`v_release_instrument`) | **8,706** |
| Unreleased | **90** |
| Pending contents gaps (`v_toc_gap_pending`) | 730 rows across 50 instruments |
| Last migration applied | `0068_segmentation_profile_v5` (69 migrations recorded) |
| Tests on the code touched since the last commit | pass (`test_verify_extraction`, `test_verify_ocr`, `test_k4_rules_rsuv`, `test_multi_instrument`, `test_instrument_supersession`, `test_patch_promoted_revision`, `test_series_regulation`, `test_ocr_correction_script`) |

`CLAUDE.md` still quotes 4,687 / 4,084 / 603. That is the signed 23 Sep checkpoint; the 20–21 Oct recrawl of every
reachable official portal grew the corpus (released 4,744 → 7,166 on 21 Oct, per the log), and the 22 Oct–5 Nov queue
work took the release count to 8,706. `CLAUDE.md` has not been updated for this — see §9.

**Nothing from 22 Oct onward is committed.** The last commit is `54989ab` (21 Oct). Branch `corpus/l2-tooling-and-quality`
carries 18 modified files, ~330 untracked files (283 under `tools/recrawl/`, 109 multi-instrument plans) and two
migrations that are already applied to `nizam_clean`. See §6.

---

## 2. The 90 unreleased expressions

An expression is released only when it has no pending S7 unit, no pending contents gap, no pending boundary, a passing
document quality status and a `segmented` run (`v_release_instrument`). Counts below are `toc` / `s7`, measured today.

**Seven are held by quality status only (no gaps at all):**

| doc | pages | quality | note |
|---|---|---|---|
| 8364 Income Tax Act 1872 | 59 | `review` | |
| 9176 Mahendra Partab Singh Estates Act 1923 | 9 | `review` | |
| 9633 West Pakistan (Adaptation and Repeal of Laws) Act 1957 | 83 | `review` | |
| 9764 West Pakistan (Adaptation of Laws) Order 1955 | 89 | `review` | |
| 9852 NEPRA (Uniform System …) | 100 | `missing_evidence` | |
| 9853 Finance Act 1986 | 190 | `missing_evidence` | |
| 9854 Finance Ordinance 1981 | 199 | `missing_evidence` | |

Not investigated this session; first step is `v_document_quality_status` for each to see which criterion holds it.

**Smallest remaining (1–3 units) — the cheapest next releases:**

- S7 only: 5857 Provincial Insolvency Act 1920 (1), 9281 Probate and Administration Act 1881 (1), 9607 Lunacy Act 1912 (1),
  5485 Finance Act 2012 (1, 762 pp), 8539 FGEHA Joint Venture (2), 9302 Oudh Rent Act (2), 9326 Finance Act 1988 (2),
  9738 Navy (Discipline) Act (2), 5821 KP Higher Education Academy (3), 9308 NWP Land-Revenue Act (3).
- Contents gaps only: 9617 Masters and Mates Rules (1), 9704 ICT (Zoning) Regulation (1), 9849 Delhi Muslim Wakfs Act (1),
  7355 Customs Rules (2), 9182 Constituent Assembly Standing Orders (2), **9694 Sindh Agriculture Produce Markets Act (2)**,
  5865 KP Delegation of Financial Powers Rules (3), **9608 Patents and Designs Act 1911 (3)**.
- Mixed: 9306 Inland Emigration Act (1 toc, 2 s7).

**Medium (4–15):** 5826, 9294, 9487, 9632, 5872, 9290, 9322, 9415, 9534, 9597, 9604, 5494, 9307, 9361, 9546, 9638,
9664, 9283, 6715, 9251, 9300, 9320 (Codex-reserved, below), 9621, 9786, 8557, 9250, 9316, 9510, 9581, 9641, 5827, 9305,
5788, 9314, 9592, 9595, 5054, 6090, 9583, 5507.

**Heavy (16+):** 9575, 9603, 9568, 9613, 9584, 9636, 9601, 9606, 7064, 9618, 8590, 9612, 9596, 5790, 9642, 7318
(Estacode, 1,042 pp, 31 s7), 7968, 9298, 5864 (47 s7), 5504, 9631, 9639, 9321 (CrPC 1898, 89 toc), 5016 (108 s7).

Re-derive the list at any time with `tools/recrawl/rel.sh` and the query in `tools/audit/blocked-release-worklist.sql`.

### In flight when the session stopped

- **9608** (Patents and Designs Act 1911, 44 pp, 3 contents gaps, text gate passing) and **9694** (Sindh Agriculture Produce
  Markets Act 1939, 22 pp, 2 gaps — junk rows like "avilled …" read from body text): triaged only. `secs.sh` listings
  were read; `mkread.sh` was the next command. Nothing was recorded on 5–6 Nov for either. **9608 does have older records**
  (suffixes `v`/`v2`, 30 Oct) that placed contents rows; it stayed held on 3 contents rows and an unresolved page-12
  set-aside anchor (the `v3` run stopped). Check `units_for.py 9608` and the active patches before adding to them.
- **6090** (Balochistan Fisheries Dept Subordinate Services Rules 1982, E2 digital text): *not released, partial work
  recorded and pinned v5.* A reviewed `source_division_openers` entry at block 1468656 (`edits-6090.json`, run `u`) opens the
  Appendix. Still open: (a) contents numbers rules 3–16 where the body prints 2 (sic), 4–7, 8 Probation … 14 Repeal and lacks
  "Trainings and Departmental Examinations" and "Confirmation" — 8 unmatched rows, needs `source_contents_row_links` plus a
  `source_incompleteness` record for the two rules the body does not print; (b) the Appendix's Part-B rows still open
  sections and the Appendix nests under Part III.
- **9320** (Merchant Shipping Act 1923, 56 pp): **reserved by Codex** on 5 Nov (“Claude retains 50-and-under queue”). Source
  preflight done (renders hashed, body starts p7, 9 Parts / 296 sections, Schedules pp52–56); `116(1)(b)(ii)` has faded words that
  need a refetch or further source check, not reconstruction. No release claimed; no corpus mutation. Resume notes:
  `codex-2026-11-05-d9320/RESUME.md`. Check whether Codex is still working it before touching it.

---

## 3. What this stretch of work released (22 Oct → 5 Nov)

Counts are the release total after each step, from the log.

- **22–25 Oct** — owner policies recorded in `decision-review-2026-10-22-q22.json`: **q2 keep-both** (a number the Gazette prints
  twice in one parent stays citable, the second cited "34 (second)") and **q1 split** (a PDF binding several laws becomes one
  expression per law). Splits, owner OCR exports and re-OCR batches, single- and two-unit sweeps: 8,286 → 8,488 over rounds 1–8.
  25 Oct: the owner delegated all remaining decisions to the recommended option (memory `owner-delegation-recommended-choice`).
- **25–28 Oct** — GPU OCR route attempts: Colab through `colab-mcp` (abandoned; the MCP server now fails to connect), then Kaggle via
  `tools/kaggle/kg.sh`. 28 Oct: 7550 released with the illegible-print marker `[illegible]`.
- **29 Oct** — held OCR revisions released smallest-first. **Five documents were released with visibly wrong text and repaired the
  same night; an audit flagged 494 of 803 released OCR revisions.** This is the origin of the leakscan rule (§5).
- **30 Oct** — VLM pilot outcome (log line 2696). A Qwen2.5-VL draft released 9594 only after ~25 errors it left were found by
  reading every page. Finding: 128 of the 150 held documents already passed the text gate and were held only on S7/TOC items, so
  the VLM path (which helps only the 22 text-held ones) was **parked** and work returned to the structural queue, smallest
  first. Also: a text-gate PASS is not release-ready (9716 passed it while reading “AadFionel Iudgee”) — every held OCR document
  gets a page read. 9594, 9716 and 9842 were released that day (8,643 → 8,645+).
- The VLM draft was also wrong in the tariff tables of 9212 (it read 1½ where the page prints 1⅓), found on 5 Nov.
- **31 Oct** — source-incomplete releases (owner: "release further, and if needed add source incomplete").
- **3–5 Nov, Codex** — over-50-page items: 9615, 5814, 9765, 7511, 9851 (tariff), 9624, each “run p”.
- **5 Nov, Claude** — 9171; owner desk readings and ChatGPT-corrected OCR exports taken in (originals kept as
  `*.as-received.json`):
  9155→**9857**, 9010→**9858**, 8968→**9859**, 9291→**9861**, 9275→**9860** (split into three on q1; the 2021 notification's
  inserted Schedule III(a) is kept as the amendment's text), 9580, 9212, 9856, 9843, 9559, 9566, 4994→**9862**, 7796,
  5104→**9863**, 9848. Count 8,695 → **8,706**.

---

## 4. Defects found and corrected in this stretch

1. **Block-id pins leaking into provision text** (5 Nov). A pin (`@2679267 `) was recorded as literal text in released documents
   9212 (5 provisions), 9856 (12), 9858 (1), 9859 (7) and 9566 (1). Causes: `tools/recrawl/txedit.py` collapsed the blank line
   between *any* `| ` line and a following pin; `tools/recrawl/pack.py` kept whitespace-only lines inside a paragraph, so the page
   was "homed" and every pin became text. Fixed in both, and `pagewrite` now refuses a page mixing pinned and unpinned paragraphs
   and a pin that does not open its paragraph. All five re-recorded and still released. A scan of every released provision's latest
   version finds no `@<6–8 digits>` token.
2. **9843 (Indian Forest Act 1878) released from the wrong reading.** The released text was the earlier desk pages, not the owner's
   later full proofread (`D:\Download\9843-forest-act-proofread.json`), and still carried garbled OCR (s.11, s.12, p.2 contents
   rows, s.83's side note). Re-read from the proofread against the renders; runs `s` retired, `t` recorded (92 records, 0/0/0).
3. **`blk2read.py` AUTO set aside bare `PART I.` division headings** along with the bracketed running head `PART IV]` (doc 9848).
   Pattern now needs the bracket. Earlier readings had only set aside Gazette-part markers on title pages — spot-check any
   reading made before 5 Nov for a lost `PART` heading.
4. **`blockfix.py` anchor overflow** (9848): a page set aside whole anchored on its longest block, a 3.6 kB Index column, whose
   record overflowed the patch table's unique index row, so run `a` recorded nothing and said so only in the apply step. The anchor
   is now capped at the index row size. Lesson: a dry run reporting “would record 149” is not proof that the apply succeeded —
   re-check the count.

### Corpus finding, not fixed — needs one owner decision

**104 released documents, 1,955 provisions, carry `―…‖` where the page prints “…”.** A Word symbol-font mapping in the PDF text
layer; `verify_extraction` passes because Poppler reads the same characters, and no gate tests for it. It needs one reviewed,
corpus-wide rule (a release-view rendering rule, or reviewed readings), not per-document patches. Doc 9863 was fixed by hand
(22 pairs).

---

## 5. The release procedure that works (and its gates)

For one unreleased, promoted document. Paths are WSL (`/mnt/e/Nizam_e_Qanoon`); run through PowerShell + `wsl`
(memory `nizam-tool-invocation`; the Bash tool mangles `/mnt` paths).

1. **Look** — `tools/recrawl/units_for.py DOC` (open S7 units, contents gaps), `tree.py DOC`, `blocks.py DOC P1 P2`,
   `render_many.sh 70 DOC:PAGE` then *view the PNG*. Never write a reading from extracted text alone.
2. **Pin the profile first** — `pinonly.sh DOC "reason"` (= `tools/pin_segmentation_profile.py --profile unreleased-v5 --apply`).
   The default profile loses a division heading that follows the enacting formula; a released document cannot be re-pinned
   (memory `pin-profile-before-release`). Dry-run `segtry.py` on `default` vs `unreleased-v5` when unsure.
3. **Read the pages** — write `specs/read-DOC.txt`. Hard documents: page-by-page transcription from the renders (zoom 200–220 dpi
   with `cropzoom`). Documents with an owner export: `desk2export.py` / `takeexp.py` → `rvgo.sh` (adjudicate → withdraw
   overlaps → promote → pin v5 → segment check) → `rv2read.py` builds the reading. Documents whose text is right but whose blocks
   need pinning: `bgo.sh DOC SUFFIX` (`blk2read.py AUTO` sets aside running heads, page numbers, marginal-heading brackets, “—contd.”
   headers; `bodystart.py` pins the body start at the long title or preamble).
4. **Record + replay** — `packgo.sh DOC SUFFIX` → `pack.py` → `vgo.sh` (`record_curation_patch.py --readings … --apply`, then
   re-segment). `KEEP_EDITS=1` keeps `edits-DOC.json` (body start, `source_division_openers`, `source_text_units`,
   `source_table_row_blocks`, `source_apparatus_blocks` …). Suffixes (`a`, `b`, … `p`–`u`) number the runs; a wrong run is
   retired with `retire_patch.sh`, never deleted.
5. **Verify** — `rel.sh DOC` must show `released` with `0/0/0` (S7/TOC/boundary). Then **`leakscan.py DOC`** and read
   `ptext.sh DOC .`. Counters do not see side notes, running heads, footnotes parsed as sections, regulations read as
   sub-sections or missing pages (memory `release-gate-leakscan`). The text gate (`textgate.py`) measures real-word share only.
6. **Never** run `verify_ocr` in bulk on held revisions (10 were auto-released unchecked on 30 Oct); per document, last, via
   `tools/recrawl/ocr_verify.sh`.
7. **Log** — append to `CLAUDE-CLAIMS.md` (doc, pages read, lane, run suffix, gate numbers, KNOWN NITs) and re-baseline the count.

Special routes: **split documents** (q1) must never get a plain `patch.sh` replay (it rebuilds one tree and undoes the split) —
record the patch then re-materialize with `lsplit.sh` / `split.sh`. **Text-quality holds** on U+FFFD that the source font prints as
empty boxes: `extraction_assertion` (purpose `replacement-glyph-strip`) + `tools/promote_reviewed_text_repair.py --strip-replacement`
(4994→9862, 5104→9863). **TOC dispositions** only for contents rows that themselves print [Omitted]/[Repealed]; withdraw a wrong
one through the migration-0061 tool, never DELETE (memory `toc-disposition-pitfall`). **Legal/version questions are owner decisions** —
report them, do not decide them.

### The scripts that did the work are not in the repository

The 5 Nov session's helpers lived in its temp scratchpad (`C:\Users\bilaa\AppData\Local\Temp\claude\e--Nizam-e-Qanoon\33f4a608-…\scratchpad`).
They have been **copied to `.artifacts/release-work-2026-09-24/claude/session-tools-2026-11-05/`** (126 `.py`/`.sh` files,
including `blk2read.py`, `rv2read.py`, `spread.py`, `bgo.sh`, `rvgo.sh`, `gov.sh`, `pinonly.sh`, `strip.sh`, `takeexp.py`,
`desk2export.py`, `bodystart.py`, `pinat.py`). Caveat: several `.sh` files hard-code the *old scratchpad path* in a `W=` or `S=`
variable and will break when that directory is cleaned. Either keep that directory or change the variable to the copy. `.artifacts/`
is gitignored, so none of this is under version control; promoting the durable ones into `tools/recrawl/` is a §8 task.

---

## 6. Uncommitted code and what it does

Applied to the database already: `0067_instrument_supersession.sql` (append-only link table, 373 rows; an Ordinance linked to a
later Act of the same folded title per owner decision q6 of 21 Oct; does not set lifecycle status) and
`0068_segmentation_profile_v5.sql` (adds `unreleased-v5` to the pin check; the new rule is `toc_promised_next_section`, motivated by
the Opium Act 1878, doc 9127). Both are untracked in git.

Modified, with the reason:

| file | change |
|---|---|
| `nizam/corpus/segment.py` (+283) | `unreleased-v5` profile + `toc_promised_next_section`; `reviewed_table_block_shape_ok` / `source_reviewed_table_blocks`; lettered reviewed-bracketed-rule labels (`9A`, doc 8311) |
| `nizam/workers/segment.py` | accepts the new reviewed keys |
| `nizam/workers/verify_extraction.py` (+48) | `reviewed_replacement_strip` / `credit_stripped_replacement`: credits missing U+FFFD only up to the count a reviewed strip removed, only while its assertion is active and the repair dropped/replaced no block |
| `nizam/workers/verify_ocr.py` (+125), `ocr.py` | `nizam.verify_ocr/5` and `/6`: Q1 review resolved only by recorded evidence — `ocr-page-read-document` assertions (render digest per page), and the corrected-reading case bound to the current provision hash (`reviewed_provisions_sha256`); table-vocabulary opt-in for 9851 |
| `tools/record_curation_patch.py` | `observation_rows_for_patch`: use a promoted same-file revision before its first materialization |
| `tools/materialize_multi_instrument.py`, `tools/evidence/adjudicate_ocr_review_export.py`, `tools/recover_page_ocr.py`, `tools/recrawl/land_missing.py`, `tools/recrawl/probe.py` | supporting changes for the split, export and recrawl lanes |
| `docs/CORPUS-CRITERIA.md`, `docs/SEGMENTATION-PROFILES.md` | “as built” corrections for the above |
| `.mcp.json` | adds the `colab-mcp` server (currently fails to connect; Colab route abandoned) |
| `nizam/workers/segment.py.orig` | stray merge/patch leftover — delete, do not commit |

New tests: `test_instrument_supersession`, `test_ocr_correction_script`, `test_patch_promoted_revision`, `test_series_regulation`,
and `test_reviewed_{cp_tenancy,limitation,order,oudh,regulations}_intro` / `test_reviewed_tariff_blocks`.

**Risk:** the database runs rules and migrations that exist only in the working tree. A fresh clone of the last commit cannot
reproduce the released state. Committing is the single most valuable next action (§8.1). Per `CLAUDE.md` it needs the
`Co-Authored-By` trailer and a branch, and it is the owner's call to push.

---

## 7. Coordination and standing rules

- **Codex runs in parallel** on over-50-page items and writes its own claims to the same log. Reserve a document in the log before
  mutating it; check the log tail first. Claude's lane: 50 pages and under (memory `release-work-parallel-with-codex`).
- **Owner delegation (25 Oct):** decide every owner question with the recommended option; never hold or partially release
  (memory `owner-delegation-recommended-choice`). The one boundary: legal or version questions stay with the owner.
- **Never decrease the release count.** Work only on unreleased documents; if a replay could un-release another, stop.
- **Release is not “counters at zero”.** A tree known to be wrong is not released, even on delegation.
- The owner proofreads in parallel (`D:\Download\*.json`, exports under `.artifacts/ocr-review-exports/`). Verify their readings
  against the render before trusting them — 9843's proofread still left side notes in the text.

---

## 8. Next steps, in order

1. **Commit the working tree** on `corpus/l2-tooling-and-quality`: migrations 0067/0068 with their tests, the segmenter/verify
   changes with their tests, the docs “as built” notes, `tools/recrawl/`, the multi-instrument plans and evidence SQL as separate,
   named commits. Delete `segment.py.orig`. Decide whether `.mcp.json` belongs in the commit.
2. **Run `./nz audit`** and the full `./nz test` and record the result. I did not run the audit while writing this, so the audit
   status at 8,706 released is unverified here (the last figure I can cite is 35/35 on 20 Oct). Report the number; do not
   encode it (the tripwire rule).
3. **Update `CLAUDE.md`** current-state paragraph and `docs/RELEASE-ALL-HANDOFF-2026-09-23.md`'s pointer to this file.
4. **The seven quality-held documents** (§2): read each one's `v_document_quality_status`, which criterion is `review` /
   `missing_evidence`, and what evidence resolves it. Cheapest block of the queue — none has a structural gap.
5. **9694, then 9608** (restart both from a render), then the 1–3-unit documents in §2.
6. **6090**: the three remaining items in §2 “In flight”.
7. **Owner decision needed:** the `―…‖` quotation-mark mapping across 104 released documents (§4).
8. **Promote the scratchpad tools** (§5) into `tools/recrawl/` with relative paths, and add the regression tests the pin-leak fix
   deserves in `tests/` (pin after a `| ` row; whitespace-only line inside a paragraph; page mixing pinned and unpinned paragraphs).
9. Leave 9320 to Codex unless its reservation is released in the log.

If a step is unclear, take the smallest slice, finish it, log it, and re-baseline the count before starting the next.

---

## Addendum — same day, later (solo Claude session, no agents)

Released 6 Nov after the handoff above was written (counts from `rel.sh`; Codex releases also move the total):
**9704** (Islamabad Capital Territory (Zoning) Regulation 1992) and **8539** (FGEHA Joint Venture Projects Regulations 2020) — both
logged in `CLAUDE-CLAIMS.md`. Release count 8,709 at the end of that session. Codex still holds 9320.

What the two documents taught (in addition to §4/§5 above):

1. **One pending unit says nothing about the tree.** 9281 (one S7 unit), 9704 (one contents row) and 8539 (two S7 units) all had
   trees that were structurally wrong or full of OCR damage; the counter was a symptom. Triage by `tree.py` and `leakscan.py` plus a
   look at the renders, never by the unit count.
2. **A digital-looking lane is not a clean text layer.** 8539 is lane E2 yet carried ~60 OCR errors in the annexes and every
   regulation's item letters detached from their texts. Run `textgate.py` and read `unk`-style out-of-vocabulary words before
   calling a release done (the first 8539 release read FAIL 96.0% and was fixed the same hour).
3. **Printed typos stay.** Check each odd word against the render: in 8539 about as many oddities were printed ('tranfer',
   'brone', 'consortiumes', 'guidlines') as were OCR damage.
4. **Re-transcribing a block a second time** leaves the older record with an identical `before_text`; replay then fails
   `before_text is not unique` and `retire_changed.py` does not catch it. Retire the older of each active pair
   (`session-tools-2026-11-05/retire_dupes.py OBS --apply`) and replay (`rereplay.sh`). The replay rolls back on failure, so a
   release is never lost.
5. **Cost per document is high.** 9704 (17 pp) and 8539 (37 pp) each took a full page read. At this rate the remaining 88
   expressions are a multi-session job; the cheapest are the digital documents with real structure, then the short E4 scans.
   Still open in the 1–3-unit tier: 9281, 9607, 9849 (all scanned gazettes, trees wrong), 5857, 9694, 9608, and the seven
   quality-held documents.

Scratch helpers used (`mk.sh`, `lk.sh`, `tr.sh`, `swapply.sh`, `mytx.sh`, `rereplay.sh`, `retire_dupes.py`, `unk.py`, `ctx.py`)
are in `.artifacts/release-work-2026-09-24/claude/session-tools-2026-11-05/`; several hard-code that session's scratchpad path.

### Addendum 2 — later the same day

Released after the first addendum: **9415** (Sind Cotton (Control) Act 1954, from the owner's proofread
`D:\Download\9415-sind-cotton-control-proofread.json`; its pp14–15 were the contents of a different law, the Sind Village Sanitation
Act 1955, set aside) and **9534** (Paper Currency Act 1871, live revision **9752**). Release count 8,711.
**9575** (N.W.P. and Oudh Municipalities Act 1873) is read in full but not released — see its claims entry (section 5 will not open).

New facts, in addition to the five lessons above:

6. **Check `document.is_active` first.** 9534 was an inactive revision whose instrument was still active; the live document was 9752
   (promoted OCR revision, own block ids, quality `missing_evidence`). A run recorded against the old id silently recorded patches
   and replayed nothing (`nothing to segment`). The release also needed `ocr_verify.sh 9752`.
7. **Do not transcribe page-bottom catchwords** (the word or line at the foot of a page that repeats the next page's first words,
   including phantom '26. Every' / 'CHAPTER V.'). They duplicate text and open phantom units.
8. **The recorder refuses a patch identical to a retired one**, so re-recording after a clean slate needs fresh locators
   (`relocate3.py`). A replay that says 'matched 2 blocks' is *not* fixed by retiring that patch: you lose a real correction
   (`replayloop.sh` does exactly that — use it only on documents you will re-check line by line).
9. **A lost printed number is a segmenter problem, not a text problem.** 9575 s.5: the OCR block is 'Power-to ©. For the purposes…';
   a text patch to '5. For the purposes…' (even with `extracted_number`/`printed_number`) did not open the section.
10. Contents split over a page, or longer than ~1,000 characters, is cut by `pack.py`; pin each contents paragraph to its block.
11. Clearing an observation's patches retired 20 `codex.source-page-review/1` patches of 30 Oct on 9534's observation (12859).
    They are retired, not deleted; tell Codex (clear `retired_at` on them to restore).
12. Owner proofread files (`D:\Download\*-proofread.json`, format `nizam.desk-pages/1`) are the fastest route: `desk2read.py` builds the
    reading (side notes set aside; margin headings are NOT carried — appended to the previous section by `pack.py` otherwise).

### Addendum 3 — third stretch of 6 Nov

Released: **9583** (Legal Practitioners Act 1879), **9584** (W.P. Small Industries Corporation Ordinance 1965), **9592** (W.P. Board of
Intermediate and Secondary Education, Peshawar, Ord. 1961), **9595** (the Lahore twin, Ord. 1961), each from a full read of the renders
(claims log has the per-document detail). Release count **8,715**. Corrections to the earlier lessons:

13. **`replayloop.sh` is unsafe** — see the process-correction entry in the claims log: it drops real corrections. Use `relocate4.py`
    (safe locators) + `replaysafe.sh` (reports, never retires). Both are in `session-tools-2026-11-05/`, as are `flow.sh`, `flow2.sh`
    (clean slate + flow), `asm*.py` (reading assemblers), `toc.sh`/`toc9595.py` (contents-gap adjudication).
14. **Pin the contents** (one paragraph per OCR contents block, short blocks under 12 characters merged into a neighbour) or the ledger
    merges rows and a later schedule's article '2' steals section 2's heading.
15. **Schedule articles that the ledger leaves 'unmatched'** are settled by `adjudicate_toc_from_source.py` `found_elsewhere` readings naming
    the schedule clause — documented lane; do not alter the printed text to force the match.
16. Twin Ordinances (Peshawar 9592 / Lahore 9595) share layout and phrasing; the second took about a third of the effort.

### Addendum 4 — **9281 is released with a wrong structure (fix first)** — *fixed, see Addendum 5*

`9281` (Probate and Administration Act 1881) was released on the owner's proofread (count 8,716) but its tree is wrong: the Act prints no
CONTENTS banner, so the contents list (sections 1–156) is parsed as 156 'sections' on pp1–3 and the real sections 4–156 are clauses. The
text is right; the structure is not, so a citation 'section 63' resolves to a contents row. Claims-log entry has the evidence and the two
ways out. **It should be treated as unreleased until fixed**, and `9281` should be the first item of the next session.

Lessons added: (17) before trusting 0/0/0, print `first_page` and `kind` counts for the sections (`SELECT first_page, count(*) ... kind='section'`);
a contents list on the same pages as 'sections' is the sign. (18) A block can be re-recorded only a few times: short blocks run out of
unique locators ('no fresh unique locator in the block') and the replay then rolls back to the previous tree. Plan one batch per document; test
structural overrides on a single-page patch first. (19) A page that holds contents and the long title in one OCR block cannot take
`source_body_start_block`; use `source_contents_marker_blocks` on a block that holds only the contents head.

### Addendum 5 — 9281 fixed and released (6 Nov, later)

`9281` is now released with a correct tree: 156 sections on pp4–16, none on the contents pages, 0 duplicates, text gate 97.8%,
leakscan clean, verify_ocr run last. Release count **8,716**. How:

- The contents list is fenced with a reviewed `source_contents_region` (first 2431957 on p1, last 2432065 on p3, body start 2432067 on
  p4, rows `sections`). The long title and the preamble's first line, which sit at the foot of p3 in the same OCR block as rows 104–156,
  were re-read into the body's first block 2432067 (with page 3's reading trimmed to match), so the region can end at row 156.
- Retiring the old 2432067 record also dropped page 4's 33 apparatus blocks, which gave a duplicate section 4. They were re-added on an
  identity record.
- The region still left 8 synthetic contents gaps ('51.52', '67.68.69', …). Raw OCR contents blocks that the page readings set aside
  were still parsed as rows, because the contents parse runs before apparatus is removed. Fix: a new optional field
  **`skip_apparatus: true`** on `source_contents_region` (`nizam/corpus/segment.py`, rule `reviewed_contents_region`) reads the region's
  rows without the reviewed `source_apparatus_blocks`. The field is opt-in, so the 36 released specs without it are read exactly as before
  and no new profile is needed. Tests are in `tests/test_contents_region_skip_apparatus.py`.

Lesson (20): when a contents region carries set-aside raw OCR blocks, record it with `skip_apparatus: true` from the start.
