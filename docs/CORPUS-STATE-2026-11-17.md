# Corpus state — 17 November 2026

**This is the live continuation point.** Read it before any corpus mutation. It
supersedes `RELEASE-ALL-HANDOFF-2026-09-23.md` and
`RELEASE-QUEUE-HANDOFF-2026-11-06.md`; those, and the other dated reports in
`docs/`, are kept unchanged as the record of how the corpus got here.

Every count below was read from `nizam_clean` on 17 November 2026. Re-derive any
number with `./nz audit`, `./nz state` or the queries in `docs/SCHEMA.md`; do not
copy a number from here into a criterion (CLAUDE.md: assert the rule, report the
number).

## Where the project is

| Layer | State |
|---|---|
| L1 corpus | **Done for every law with a text layer.** Scans that need OCR are not landed (owner rule, 14 Nov). |
| L2 legal data | **Done.** Every released law is served as at a date and in a territory. Status, dates, extent and repeals are recorded. |
| L2 retrieval storage | **Not built.** No `chunk` table, no embeddings, no BM25 or vector index. `vector` 0.8 and `pg_search` 0.25.6 are installed and unused. |
| L3 retrieval and above | **Not started.** |

The next slice is the `chunk` table and the BM25 index over released provision
versions (docs/03 §3, docs/04), measured against golden sets 1–4.

## The corpus

| | |
|---|---|
| Laws released | **10,342** — none held (the 25th–27th Constitution Amendment Acts added 18 Nov, D-076; doc 1336, the Sindh Cultural Heritage Act 1994, held, repaired and released again 18 Nov, D-078; docs 4788, 4986 and 5133 likewise, D-080). 147 more active rows are exact duplicates linked by `duplicate_of` |
| Released provisions | 1,172,566 (17 Nov count; doc 1336's repair, D-078, removed one false sub-section) |
| Released pages | 134,982 |
| Active documents / characters | 10,188 / 270,129,040 |
| Source observations | 10,394; 66 catalogue items are declared acquisition exceptions with dated evidence |
| Active provisions (incl. linked duplicates) | 1,197,584 from 202,604 sections — tree expansion 5.91× |
| Amendment references | 15,184 |
| Statutory repeals / territorial repeals | 215 rows, 180 standing / 48 (three are whole repeals that except units, 17 Nov; the 48th, the 1975 Antiquities Act in Balochistan, 18 Nov, D-078) |
| Partial repeals / units a repeal excepts | 34 units in 12 laws / 16 units in 2 laws (0102, 0103) |
| Migrations applied | 103 (last 0103) |
| Database size | 4.8 GB after the 17 Nov cleanup |
| Audit | 41 criteria, all pass (A19 added 18 Nov) |

### By jurisdiction

| | Released | Served directly | Current | Not current | Historical |
|---|---|---|---|---|---|
| Federal | 3,562 | 3,511 | 2,429 | 411 | 671 |
| Sindh | 2,004 | 2,004 | 1,713 | 291 | 0 |
| AJK | 1,442 | 1,442 | 808 | 634 | 0 |
| Punjab | 1,366 | 1,366 | 1,346 | 16 | 4 |
| Balochistan | 1,030 | 1,030 | 1,020 | 9 | 1 |
| KP | 911 | 911 | 903 | 8 | 0 |
| Gilgit-Baltistan | 27 | 27 | 27 | 0 | 0 |
| **Total** | **10,342** | **10,291** | **8,246** | **1,369** | **676** |

The 51 federal laws released but not served directly are as-made Gazette texts.
Each is served through its consolidated text (`consolidated_twin`, 0075).

**Not current** means repealed, lapsed (an Ordinance past its constitutional life,
0091), replaced or superseded. **Historical** means one of three things:
- a pre-1947 text that no official consolidation carries (549);
- a law of a place outside Pakistan (117);
- rules under such a law (10).

Laws whose force could not be verified are presumed in force (owner decision, 16 Nov). The presumption never
covers a pre-1947 archive text, whatever its kind. Correcting 6688's kind showed that Ordinances had escaped that
rule, and 31 such Ordinances moved from current to historical on 17 Nov.

### Not landed

- **AJK: 874 scans; Gilgit-Baltistan: 151 scans.** They need OCR, which is not run
  for now (owner rule).
- **Gilgit-Baltistan, other:** 13 non-PDF captures, 4 errors, 2 partial captures;
  2 text-layer Acts were blocked at preflight.
- **Gilgit-Baltistan Assembly portal:** all 26 Act PDFs return 404, recorded as
  acquisition exceptions. The 27 landed GB Acts come from Internet Archive
  captures of the official `gba.gov.pk` URLs, SHA-1-checked against the archive.

## How the law is read

Application reads go through `operative_provision` and nothing else (INV-5):

```sql
SET nzq.as_of = '2026-11-17';     -- required; the view refuses without it
SET nzq.territory = 'punjab';     -- optional: punjab sindh kp balochistan ict ajk gb
SELECT * FROM operative_provision WHERE ...;
```

- **Territory.** A law is served where its own extent clause says it runs
  (`territorial_extent`, 0095). Where no extent clause was read, the title
  decides. A territorial repeal removes a federal-text law from one province
  from its exit date (`territory_exits`, 0095, NULL-safe since 0100).
- **Older dates.** `text_known_from` (0096–0099) is the earliest date the held
  text is known to be the law. It is decided per law:

  | Basis | Laws | Provisions |
  |---|---|---|
  | `no_amendment_recorded` | 6,022 | 433,165 |
  | `after_latest_recorded_amendment` | 376 | 39,555 |
  | `an_amendment_is_undated` — served only from capture | 3,856 | 652,601 |

- **Serving snapshot.** `mv_instrument_serving` and
  `mv_provision_text_known_from` are materialized. Run
  `tools/refresh_serving.py` after any recorder; audit A16 fails while either is
  stale.

## Golden sets (docs/10 §4)

| Set | Cases | Focus |
|---|---|---|
| 1 | 50 | mixed baseline |
| 2 | 50 | the core codes |
| 3 | 50 | jurisdiction and temporal pairs |
| 4 | 50 | labour, tax, IP, Rules |

Each set has the strata 20 citizen / 12 professional / 8 procedural / 5 Urdu /
5 unanswerable. Every necessary unit's text is checked by a regex against the
held text, and all four build with 0 problems (`evals/golden/README.md`).

200 of the 500 target cases are built. **The review sheets
(`evals/golden/review/`) are blank, so Cohen's κ is not yet measured.** That
review must happen before any threshold is tuned.

## Storage

| | |
|---|---|
| Database on disk | **4.8 GB** after the 17 Nov cleanup (was 5.6 GB) |
| Largest tables | `provision_version` 1,015 MB · `text_block` 822 MB · `provision_ancestor` 738 MB · `provision` 693 MB · `provision_block` 506 MB · `segmentation_curation_patch` 321 MB · `instrument_revision_archive_manifest` 215 MB |

### The 17 Nov cleanup (prune batch 6, then compaction)

1. **Archive first.** The full dump `nizam_clean-20261116T201452Z.dump` was
   taken and its sha256 recorded in `revision_archive_batch`. A protected copy
   sits outside snapshot rotation in `E:\nizam-data\archives\prune-2026-11-17\`.
2. **Isolated proof.** `tools/test_prune_retired.sh` ran the prune on a
   restored copy. The signature of source evidence, active trees and release
   was identical before and after, including a hash of every released text, and
   the audit passed on the copy.
3. **Live prune.** 1,620 superseded revisions were archived with a manifest row
   each and then removed: 167,035 provisions, 160,635 versions and 323,861 block
   links. 1,579 retired revisions remain on purpose, because evidence still names
   them (identity proofs, contents decisions, heading census, manifests).
4. **Compaction.** `VACUUM (FULL, ANALYZE)` took the database from 5,648 MB to
   4,803 MB. The ~0.6 GB of dead space and index bloat that updates had left went
   with it.
5. **Gates after.** Audit 39/39; 2,062 tests pass, 36 skipped, 0 fail. All four
   golden sets build with 0 problems and their content is unchanged.

What is left is the law, its evidence and 1,579 evidence-bound retired revisions.
The project's append-only rule keeps the evidence, so this is close to the floor
for the master copy.
- **Snapshot folder (~12 GB, on E:, outside the database).** Interrupted
  `.partial-*` dumps take 6.0 GB. Dumps of the retired `nizam` database take
  2.2 GB. Superseded 16 Nov `nizam_clean` snapshots take 5.1 GB. Keep
  `nizam-clean-pre-toc-prune-20260904.dump` and
  `nizam-clean-pre-v5-prune-20260906.dump` (archives of prune batches 1–2),
  `archives/prune-2026-11-11/` (batch 5) and `archives/prune-2026-11-17/`
  (batch 6).
- **Missing prune archives.** The archives for batches 3 and 4
  (`nizam_clean-20260909T075441Z.dump`, `nizam_clean-20260909T192458Z.dump`) are
  no longer on disk. Snapshot retention removed them. Their manifest rows
  remain, but those two prunes can no longer be restored from a dump.

## Moving the database to another machine

```bash
./nz export                    # 624 MB dump + sha256 + manifest.json under snapshots/exports/
./nz export --physical         # 1.3 GB byte-exact copy of the whole cluster
# receiver: same commit, ./nz up, copy the folder into snapshots/exports/, then
./nz restore exports/<name>/<name>.dump
./nz restore --physical [--verify] exports/physical-<stamp>
```

Both formats carry every table and row, view, materialized view, function,
trigger, foreign key, index, extension and the migration history. Both check
their checksums and recompute the corpus signature, which must equal the
manifest's. Tested 17 Nov, after the cleanup:

- **Dump:** restored into a scratch database in 6 minutes; signature matched;
  audit 39/39.
- **Exact copy:** started in a throwaway container 43 s after unpacking began;
  signature matched; audit 39/39.

The exact copy's replace mode, which swaps the copy into a live pgdata volume,
has not been run on a second machine. See `SETUP.md`, path A.

Current exports: `snapshots/exports/nizam_clean-20261116T203931Z/` and
`snapshots/exports/physical-20261116T205051Z/`.

## Before any corpus mutation

1. Stage, then `preflight_segment.py`, then `select_landing.py`, then
   `land_missing.py --staged DIR --scraper-version recrawl-YYYY-MM-DD/N`, then
   `tools/recrawl/pipeline.sh VERSION`. A landed law that fails a gate sits
   held. The rule is that nothing stays held.
2. After landing, run the recorders in order: titles, enacted dates,
   commencement, long titles, statutory repeals, repeal dating, `record_status`,
   `apply_statutory_repeals`, `apply_instrument_metadata`, territorial extent and
   repeals, `refresh_serving`, `census_heading_mislabel --record`
   (`tools/post_replay_sequence.sh`).
   Before replaying released laws, dry-run them with
   `python -m nizam.workers.segment --documents ... --redo --include-review --dry-run --release-diff OUT.jsonl`.
   The release gate's own comparison then shows whether each rebuild changes anything but what you intended.
3. Run the leak scan and read the text before release. The text gate misses
   side notes, running heads and footnotes left inside sections.
4. A released law whose repair changes text needs a hold row first
   (`tools/evidence/hold-*.sql`).
5. The gates are `./nz audit` (40/40), `pytest` and the golden build
   (`evals/golden/build_set*.py`, 0 problems).

## Open items (none blocks L3)

- Undated amendment footnotes limit past-date serving to capture for 3,856 laws.
- A partial repeal whose date is not printed falls back to 1 January of the repealer's year where its
  commencement and enactment are unrecorded. For example, ETO ss.36–37 stop on 1 Jan 2016, though PECA
  commenced later that year.
- Repeals by subject ('in relation to the subject matter of this Act') and amendments of words are not
  modelled as unit repeals; they remain in the held text.

Closed 17 Nov: catalogue years and kinds (0101: 6688, 8846, 9067, 11382, 11379); partial repeals (0102) and
units a whole repeal excepts (0103), including Companies Ordinance 1984 Part VIIIA.

Closed later on 17 Nov: the federal Pakistan Penal Code (doc 4441) repaired in two held passes (DECISION-LOG
D-062 to D-064):
- 23 footnote blocks set aside and 2 re-read, removing five false sections and footnote text from about 30 sections;
- body start at CHAPTER I, so the Preamble is served;
- six inserted chapters opened (VA, IXA, XVIA, XVIIA, XVIIB, XXA).

It now serves the Preamble and 640 sections (1–511 plus 129 inserted) in 29 chapters. The tree diff showed only
footnote words removed. Audit 40/40, golden sets 0 problems.

Found while doing it: post-replay step 2c stopped on the September baseline (claude-baseline-88, 587 old
undeclared rises).

Closed in the evening of 17 Nov:
- **Release baseline re-signed** (D-067). claude-baseline-89 holds 10,339 released, and the full post-replay
  sequence runs end to end again.
- **Preamble order** (D-068). A new segmenter rule puts a preamble printed under an empty "PART I" or "CHAPTER I"
  heading ahead of it in the tree.
  - 252 released laws, the PPC among them, were replayed with ordinal-only changes. Paths, text and contents were
    proved identical, and 18,529 units were renumbered.
  - Misordered laws fell from 283 to 44. The release stayed at 10,339 and the guard reported 0 rises.
  - Post-replay step 2 still reports 19 multi-expression plans that do not re-materialise; this predates the
    replay (DECISION-LOG open questions).

Closed early on 18 Nov:
- **The Constitution's structure** (D-069). Doc 4419 now serves its real Preamble (pp17–18), Part I "Introductory"
  over Articles 1–6, and the Annex (the Objectives Resolution) as its own unit. Before, the Annex's recital was
  served as the Preamble.
  - This took two page-read readings, a hold, a replay and the full post-replay sequence.
  - 1,925 of 1,927 units are unchanged; 24 changed path under Part I.
  - Release 10,339, guard 0 rises, audit 40/40, golden sets 0 problems.
- **Instrument ids change on replay.** The Constitution's id moved from dbef70df… to 40689a31…. Collections resolve
  laws by document id, so links built from the API keep working; a stored instrument URL from before the replay
  answers "not available".

Closed later on 18 Nov:
- **Boundary evidence restored** (D-071, migration 0106, audit A19). The 11 Nov prune had deleted 226 boundary
  candidates that active expression manifests cite. They were restored from its archive records, and the prune now
  severs the link instead of deleting. 18 of the 19 multi-expression documents re-materialise again; 4347 e3 stands
  as released (older drift).
- **Gazette running heads** (D-072, rule `gazette_running_head`).
  - 445 documents were dry-run, and 230 laws passed a word-exact proof.
  - 225 were replaced; the release gate refused 5, which stand.
  - Misordered preambles fell from 44 to 38. 155 Gazette laws keep their false Parts until a page-read repair.
- **Audit:** 41 criteria (A19 added), all pass. Release 10,339, guard 0 rises.
- **Constitution amendment Acts 23rd–27th:** not landed (D-074). The official Gazette scans have poor OCR text
  layers and are staged for the OCR lane.
- **25th, 26th and 27th Amendment Acts landed and released** (D-076, owner instruction).
  - All 43 pages were read from the images and checked against the scans' OCR layer and a Kaggle Qwen3-VL reading;
    every disagreement was settled on the image.
  - Quoted Constitution text stays inside the provisions that insert it (27th: Chapter 1A, Articles 175B–175L).
  - The new rule `reviewed_comma_section_label` covers the 27th's s.45, printed "45,".
  - Release 10,342 (federal 3,562), served directly 10,291, current 8,246. Audit 41/41; golden sets 0 problems.
  - 38 `amends` edges now resolve into the Constitution. The 23rd and 24th stay unlanded: no official Act text.

Still open:
- Golden sets 5–10, and annotation of sets 1–4.
- No Urdu statute text is landed. Sindh Urdu PDFs exist, but their text layer is
  reversed, so they must not be extracted as-is.
