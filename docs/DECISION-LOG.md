# Decision log

Every decision that shaped Nizam-e-Qanoon, oldest first: architecture, corpus, linking, schema, serving, client,
process, and the owner's rulings. Each entry says what was decided, why, and where it is recorded, so any part of
the system can be traced back to the choice behind it.

This log is an index, not the specification. The sixteen documents in `docs/` remain the contract. Where an entry
and a document disagree, the document is wrong or the entry is stale, and fixing that is itself a decision to log.

## How to add an entry

- **Append; never rewrite.** Add new entries at the end with the next number. To change a past decision, add a new
  entry that names the one it supersedes (`Supersedes D-012`) and add `Superseded by D-0NN` to the old entry's
  status line. That status line is the only edit a past entry may receive.
- **Log it in the same change that makes it.** The commit that adds a migration, a rule, a convention or an owner
  ruling also adds its entry.
- **Log decisions, not tasks.** Log a choice between alternatives, a rule, a convention, a scope change or a
  ruling. Routine work that follows an existing decision is not logged (the git history has it); cite the decision
  it followed instead.
- **Each entry takes this form:**

```
### D-NNN · YYYY-MM-DD · Short title
Area: architecture | corpus | linking | schema | serving | client | evaluation | process | owner ruling
Status: standing (or: superseded by D-NNN)
- Decision: what was chosen, in one or two sentences.
- Why: the reason, ideally the failure or measurement that forced it.
- Where: commit, migration, document section, tool or test that records or enforces it.
```

Dates are the day the decision was recorded in the repository. "Owner" means the project owner's ruling.

---

## Founding architecture (28–30 August 2026)

The architecture decision records are in `docs/01-master-architecture.html` (ADR index). They are summarised here so
the log starts complete; the full reasoning stays in doc 01.

### D-001 · 2026-08-28 · Seven layers and five invariants
Area: architecture · Status: standing
- Decision: Seven layers (L1 corpus to L7 clients), each calling only the layer below it plus the shared inference
  worker. Five invariants are rejection criteria: no generated citation (INV-1), no answer without a passing gate
  (INV-2), every answer replayable (INV-3), provisions are the citable unit (INV-4), and law is answered as at a
  date (INV-5).
- Why: a legal answer that cites a wrong section, answers without grounds, or serves repealed law causes harm that
  good average performance does not offset.
- Where: docs/01; CLAUDE.md "The five invariants"; commits 9f712b0, ccb3f84.

### D-002 · 2026-08-28 · One Postgres for relational, vector, lexical and graph (ADR-1)
Area: architecture · Status: standing
- Decision: no second datastore. A chunk row and its vector are written in the same transaction.
- Why: one transaction boundary, one backup, one operator.
- Where: docs/01 ADR-1; docs/03.

### D-003 · 2026-08-28 · Hosting ladder; a single self-hosted node at full scale (ADR-1a, ADR-1f, ADR-8)
Area: architecture · Status: standing
- Decision: four hosting stages, from local Docker up to a single self-hosted node. One VPS with Docker Compose and
  no orchestrator. Rented GPUs never sit in the request path.
- Why: managed Postgres hosts only the database. Inference workers, ingest and staging still need a host, and every
  query would cross the public internet.
- Where: docs/01; docs/03a; docs/09b.

### D-004 · 2026-08-28 · Schema lives in migrations; the engine is a digest-pinned image (ADR-1g)
Area: schema · Status: standing
- Decision: the schema is changed only through numbered migrations in git, never a GUI, on one pinned Postgres
  image. Applied migrations are checksum-guarded: add a new migration, never edit an old one.
- Why: a laptop and the server must not drift, and moving hosts must be a restore, not a rebuild.
- Where: docs/01 ADR-1g; infra/postgres/migrations; CLAUDE.md "Repo layout".

### D-005 · 2026-08-28 · Binary-quantised vectors, guarded by an ablation (ADR-1d)
Area: architecture · Status: standing (not yet built)
- Decision: store vectors as `bit(1024)`, with a cross-encoder reranking by reading the text. Fall back if binary
  costs more than 2 NDCG points after reranking.
- Why: about 32 times smaller than float32 at full statutory scale.
- Where: docs/01 ADR-1d; docs/10 ablations.

### D-006 · 2026-08-28 · Published corpus scope is a deployment parameter (ADR-1e)
Area: architecture · Status: standing
- Decision: instruments are promoted to the live index by scope tag. The same schema serves a demo and a pilot.
- Why: narrowing scope to fit a host must be configuration, never a schema compromise.
- Where: docs/01 ADR-1e.

### D-007 · 2026-08-28 · Offline: a signed one-way corpus, and verified answers rather than an on-device model (ADR-1b, ADR-1c)
Area: architecture · Status: standing
- Decision: corpus patches are server-signed and one-way. User data syncs last-writer-wins. Offline answers ship as
  verified artefacts in a pack tier, not from an on-device generator.
- Why: a 1B four-bit model is about 800 MB and reasons about Pakistani law worse than the server already did.
- Where: docs/01; docs/08 §3.5.

### D-008 · 2026-08-28 · Retrieval and generation choices (ADR-2, ADR-4, ADR-5, ADR-6)
Area: architecture · Status: standing (L3/L4 not yet built)
- Decision:
  - Fine-tune the retriever and reranker; generation sits behind a provider port (ADR-2).
  - Retrieve across Urdu and English directly, not through a translation pipeline (ADR-4).
  - Roman Urdu is a first-class input (ADR-5).
  - Claim attributed generation with measured faithfulness, never "zero hallucination" (ADR-6).
- Why: equity across scripts, measurable quality, and no impossible claims.
- Where: docs/01; docs/04; docs/05.

### D-009 · 2026-08-28 · Text layer first; OCR is a fallback lane (ADR-3)
Area: corpus · Status: standing
- Decision: OCR runs only when the text layer is unusable, and how often it runs is a metric.
- Why: OCR introduces errors that a born-digital text layer does not.
- Where: docs/01 ADR-3; docs/02.

### D-010 · 2026-08-28 · Bitemporal provisions; the provision is the citable unit (ADR-7, ADR-10)
Area: schema · Status: standing
- Decision: provision versions carry validity ranges with an exclusion constraint, and no query reads them without
  a date. Chunks are derived; no chunk identifier exists above L2.
- Why: INV-4 and INV-5. Re-chunking must never break a stored citation.
- Where: docs/01; docs/03; docs/03b.

### D-011 · 2026-08-28 · A public page per provision; curation console and golden set first (ADR-9, ADR-11, ADR-12)
Area: architecture · Status: standing
- Decision:
  - The web tier is server-rendered, with a crawlable page per provision.
  - The curation console is built in phase 1.
  - The golden evaluation set is built before any tuning.
- Why: distribution and citation; and nothing can be tuned without the instrument that measures it.
- Where: docs/01; docs/10.

### D-012 · 2026-08-30 · Build one small component at a time, completely
Area: process · Status: standing
- Decision:
  - Decompose any multi-part request and finish one slice (it runs, is tested, enforces its invariants, matches its
    doc) before starting the next.
  - Work in layer order, L1 to L7.
  - Every decision cites a document. External facts (prices, limits, the status of a statute) are verified, never
    recalled.
- Why: breadth-first produces half-built modules, and remembered vendor and statute facts were wrong more than once.
- Where: CLAUDE.md "How to work here"; the `nizam-workflow` skill; commit ccb3f84.

---

## Corpus building (September 2026)

### D-013 · 2026-09 · Source and decision evidence is append-only
Area: corpus · Status: standing
- Decision: re-extraction or re-segmentation first retires the previous revision (`is_active`, `supersedes_*_id`,
  `retired_at`). Current-state queries read active views, and the application reads the narrower release views.
- Why: learned after shipping the mistake; a decision without its evidence cannot be defended or replayed.
- Where: CLAUDE.md "Two rules the corpus taught"; docs/03.

### D-014 · 2026-09 · A criterion asserts a rule, not today's count
Area: process · Status: standing
- Decision: audit criteria assert the rule and report the number.
- Why: two criteria written as fixed counts failed on healthy data within a day.
- Where: CLAUDE.md; tools/audit/criteria.sql; docs/CORPUS-CRITERIA.md.

### D-015 · 2026-09-14 · A footnote is never a section opener
Area: corpus · Status: standing
- Decision: a footnote run is apparatus wherever it sits on the page, and a footnote number may not open a section
  or set a boundary.
- Why: 142 stored "sections" were footnotes, and replaying made it worse.
- Where: commits 4530a32, 527cac1, cc41310. D-062 repairs a later case where a source's footnotes escaped this.

### D-016 · 2026-09-14 · S7 is a parser-repair queue: fix, replay, re-attach, then adjudicate
Area: process · Status: standing
- Decision: a structural collision is fixed in the parser and replayed before anyone adjudicates it. After a replay,
  the repairs run in a fixed order: re-link duplicates, re-attach source readings and contents decisions, re-derive
  metadata, refresh serving.
- Why: of 430 decisions written before one replay, 49% came back as the same collision; that reading was done twice.
- Where: commits 55fd62e, 13cdae0; tools/post_replay_sequence.sh.

### D-017 · 2026-09 · Releases are measured against signed baselines; the count may rise, never fall
Area: process · Status: standing
- Decision: every release batch is checked against a signed baseline. Every pinned released tree must rebuild
  unchanged after each parser change. No document may gain released expressions without a declared reason.
- Why: a duplicate observation once put a second, uncorrected Constitution into the release (doc 4419, 12 Oct).
- Where: tools/released_count_guard.py; post_replay_sequence.sh step 2c; tools/recrawl/pipeline.sh.

### D-018 · 2026-10-06 · An unnumbered provision is never cited as "section X"
Area: corpus · Status: standing
- Decision: a provision printed without a number gets no numeric label unless an owner decision is cited for it.
- Why: INV-1. An invented number is a wrong citation.
- Where: commit cd9937f; `is_unnumbered_provision` in nizam/shared/corpus_types.py.

### D-019 · 2026-10-06 · Segmentation profiles are pinned per released document
Area: corpus · Status: standing
- Decision: parser rules are ported into versioned profiles (unreleased-v4, then v5, pinned by 0068). A released
  document keeps its pinned profile.
- Why: a parser improvement must not silently change law that is already released. Profile v5 once merged sections
  34–85 of doc 5872 into section 33.
- Where: docs/SEGMENTATION-PROFILES.md; migration 0068; commits cd9937f, 8152788.

## Release and status (October 2026)

### D-020 · 2026-10-20 · A file that is not the law's text is kept out of release
Area: corpus · Status: standing
- Decision: an unofficial translation, or a Bill whose enacted text is held, names its authoritative document and
  is not released. A copy missing pages records source incompleteness instead of being guessed at.
- Why: only authoritative text may be served as law.
- Where: migrations 0054, 0060, 0065; audit C9; commit 6239151.

### D-021 · 2026-10-21 · Statutory repeal status only from an exact match in held text
Area: linking · Status: standing
- Decision: a released Act's whole-enactment repeal links to a held law only on a unique title, year and
  jurisdiction match, with no qualifier and no revival. The repeal date is recorded only where the repealing Act
  prints one date and commences at once.
- Why: a wrongly repealed law disappears from service, which is worse than a missed link.
- Where: migration 0066; audit A14; commit 54989ab; tools/record_statutory_repeals.py.

### D-022 · 2026-10-21 · Owner q6: an Ordinance followed by an Act of the same title is superseded, but its status is not set
Area: owner ruling · Status: standing
- Decision: link the Ordinance to the later Act (`instrument_supersession`). The link never sets the Ordinance's
  status.
- Why: the owner's answer to decision question q6.
- Where: migration 0067; commit 8152788.

### D-023 · 2026-10-25 · Owner delegation: decide with the recommended option, and never hold
Area: owner ruling · Status: standing
- Decision: questions that would go to the owner are decided with the recommended option and recorded as delegated
  decisions. Never choose "keep unreleased" or "release only part". Every page decided on is still read, and text
  seen to be wrong is fixed from the page image, never released as it is.
- Why: the owner's review time was the bottleneck.
- Where: the owner's chat, 25 Oct 2026; delegated decision exports under .artifacts/decision-review.

## L2 legal data layer (November 2026)

### D-024 · 2026-11-11 · Superseded trees are pruned only through an archive and a restore proof
Area: schema · Status: standing
- Decision: retired revisions are archived, a restore of the archive is proved, and only then are they removed.
  Revisions that any evidence still names are kept.
- Why: the database grew to 15 GB of retired trees, but evidence must never lose what it points at.
- Where: commit 5e80f0f; tools/test_prune_retired.sh; tools/prune_retired_live.sh.

### D-025 · 2026-11-11 · The release view serves one row per instrument
Area: serving · Status: standing
- Decision: as named. Doc 9164's manifest was relinked to its live tree.
- Where: commit e9f5b7e.

### D-026 · 2026-11-11 · Instrument metadata comes only from evidence, keyed by source
Area: schema · Status: standing
- Decision: display titles, numbers, dates and text language are recorded append-only, keyed by source, and derived
  in both directions after every replay. The portal's own date field is never used as an enactment date; it holds
  placeholders, upload dates and Gazette dates.
- Why: INV-1 renders citations from records, so the records must carry their basis.
- Where: migration 0070; audit A15; commit e82fde1; tools/apply_instrument_metadata.py.

### D-027 · 2026-11-11 · `operative_provision` is the only way law text is read
Area: serving · Status: standing
- Decision:
  - The view requires `nzq.as_of`.
  - It excludes repealed and uncommenced law.
  - It serves Urdu only as `text_ur`.
  - It flags commencement, invalidation and extent coverage instead of inferring them.
- Why: INV-5, and docs/03b's position that notifications are not in the statute text.
- Where: migration 0071; docs/03b §6.2 (as built).

### D-028 · 2026-11-11 · An amendment footnote links only to a unique, jurisdiction-consistent law
Area: linking · Status: standing
- Decision: an amending law is resolved from a printed footnote only on a unique match within the same
  jurisdiction. Otherwise it stays unresolved.
- Why: number series collide (West Pakistan and Bombay Acts are filed under "fed"); a number collision is not a
  match.
- Where: migrations 0072–0074; commit e82fde1.

### D-029 · 2026-11-12 · Owner: as-made Gazette texts stay citable, but only the consolidated twin is served
Area: owner ruling · Status: standing
- Decision: about 40 laws exist both as the original Gazette issue and as the Pakistan Code consolidated text. Each
  reviewed pair is linked; both stay released and citable; only the consolidated text is served as law. A repeal
  recorded on either text repeals the law.
- Why: six linked laws had their repeal recorded only on the as-made copy and were being served as current.
- Where: migrations 0075–0077; commit d6d47f5.

### D-030 · 2026-11-12 · Sindh Urdu and Sindhi texts are acquired, but never extracted as they are
Area: corpus · Status: standing
- Decision: Urdu and Sindhi files are paired with their English law by PubID. Their text layer is reversed and its
  digits remapped, so it is never extracted directly. No Urdu statute text is landed yet.
- Why: the extracted text is not the printed text.
- Where: commits 0dc6fa5, 7f9705f, 0474d44; tools/recrawl/pipeline.sh (extraction scoped to the version's blobs).

### D-031 · 2026-11-13 · A label defect is a label that breaks its neighbours' run
Area: corpus · Status: standing
- Decision: the release's label check is "does the label break the sequence of the labels around it". It is not
  "does the label disagree with its first block", which flagged mostly correct rows.
- Why: about 400 "disagreement" rows were mostly correct; the sequence break found 1,632 real ones.
- Where: tools/audit/released-label-breaks-sequence.sql; tools/audit/label_triage.py; commit 7b065cc.

### D-032 · 2026-11-14 · Owner: scope adds Islamabad Capital Territory, AJK and Gilgit-Baltistan
Area: owner ruling · Status: standing
- Decision: new sources pk-ict, pk-ajk and pk-gb. An Islamabad-only Act of Parliament stays "fed"; "ict" is for
  instruments made by ICT authorities. The segment worker refuses a source it does not know instead of falling back
  to "fed".
- Why: the owner's decision; docs/02 §2.2 already listed the AJK and GB assemblies as P1 sources.
- Where: commit dce4c70; tests/test_source_jurisdiction.py; CLAUDE.md.

### D-033 · 2026-11-14 · `legal_edge` is a view over source-keyed records, not a stored table
Area: linking · Status: standing
- Decision: the docs/03b edges (`amends`, `repeals`, later `empowers`) are resolved at read time from
  `amendment_reference`, `statutory_repeal` and the delegation records.
- Why: a stored table of UUIDs would be orphaned by the next replay (decided by the lead under the standing
  delegation).
- Where: migrations 0079, 0089; docs/03b §6; docs/SCHEMA.md.

### D-034 · 2026-11-14 · Owner: only laws that need no OCR are landed
Area: owner ruling · Status: Superseded by D-114
- Decision: scanned laws are not landed for now: 874 AJK and 151 GB scans.
- Why: the owner's rule for this phase.
- Where: CLAUDE.md "Current state"; docs/CORPUS-STATE-2026-11-17.md.

### D-035 · 2026-11-14 · Stage and preflight every law before landing it
Area: process · Status: standing
- Decision: stage the file, run `preflight_segment.py` (extract, segment and text gate), select, then land. A law
  that fails a gate after landing sits held until it is fixed.
- Why: landing first and repairing afterwards had left released law with defects.
- Where: commit ca7a89a; docs/CORPUS-STATE-2026-11-17.md "Before any corpus mutation".

### D-036 · 2026-11-15 · AJK citations never fall back to federal law
Area: linking · Status: standing
- Decision: AJK amendment and repeal citations resolve within AJK only, behind a law-stem guard.
- Why: AJK Act numbers collide with federal ones.
- Where: migration 0080; commit 752601d.

### D-037 · 2026-11-15 · A batch repair is proved by a tree diff, not a hash
Area: process · Status: standing
- Decision: every document a batch changes is checked by a word diff of its old and new trees. Afterwards the whole
  post-replay sequence runs.
- Why: a hash proof covers only what it normalises. The diff caught nine Sindh documents where setting a running
  head aside dropped the provision it opened.
- Where: commit cdf12bf; .artifacts/treediff.py.

### D-038 · 2026-11-16 · Dates and status only from printed evidence
Area: serving · Status: standing
- Decision:
  - Enactment: assent statement, then the bracket date, then the date line. The federal Pakistan Code bracket date
    is not the assent day.
  - Commencement: general clauses defaults apply only where their condition is printed.
  - In force: recorded only for commenced Acts with no repeal known.
- Why: full coverage needs Gazette notifications that the corpus does not hold, so the rest must be declared
  unknown, not guessed.
- Where: migrations 0081, 0082; commit 183f9b6.

### D-039 · 2026-11-16 · Every law has a currency and a reason; unknown is never served as current
Area: serving · Status: standing
- Decision: currency (current, not current, historical) is derived from standing records, with its reason and the
  earliest date the evidence proves the law stopped. Not-current and historical law is dropped from that date.
- Why: golden set 1 found the Prevention of Electronic Crimes Ordinance 2008 and the Companies Ordinance 1984
  served as current law.
- Where: migrations 0083–0088; commit 0c14d20.

### D-040 · 2026-11-16 · Ordinance lapse is read from the constitutions' own text
Area: serving · Status: standing
- Decision: Ordinances lapse under the article text in force when they were made: Art. 89 and 128 before and after
  2010, and AJK Interim Constitution Art. 41. Continued Ordinances amended later are tested as Acts.
- Why: 1,064 Ordinances lapsed by the constitutions' own words.
- Where: migrations 0091, 0092; commit 499f194.

### D-041 · 2026-11-16 · A serving snapshot that the audit keeps fresh
Area: serving · Status: standing
- Decision: `mv_instrument_serving` holds each law's release, currency, reach and historical window, and
  `operative_provision` reads it. Refresh it (`tools/refresh_serving.py`) after any status or record change; audit
  A16 fails while it is stale.
- Why: one territory took 7 min 25 s to serve; with the snapshot it takes 8.7 s.
- Where: migrations 0093, 0094; audit A16.

### D-042 · 2026-11-16 · Subordinate laws link to the law and section they were made under
Area: linking · Status: standing
- Decision: an `empowers` edge from the enabling law to the subordinate law, read from the subordinate law's
  printed enabling clause.
- Where: migrations 0089, 0090; commit 9447768; tools/record_delegation.py.

### D-043 · 2026-11-16 · Owner: no more online status research; unverified laws are presumed in force
Area: owner ruling · Status: standing
- Decision: a law whose status no text settles is recorded in force on the basis `owner_presumption_in_force`. The
  reason it would otherwise have had is kept in the evidence. Evidence of ending is never overridden: a statutory
  repeal, a portal repeal note, a pre-1947 archive text, or a subordinate law of a historical parent.
- Why: the owner's ruling; the remaining sources (in-force registers, commencement notifications) do not exist in
  usable form.
- Where: commit 33bdb51; tools/record_status.py (`OWNER_PRESUMPTION`).

### D-044 · 2026-11-16 · Where and when a law runs is read from its own text
Area: serving · Status: standing
- Decision:
  - A federal law's own extent clause decides its reach over the title reading.
  - "The capital of the Federation" means Karachi in laws up to 1960 and Islamabad from 1963.
  - A provincial repeal of a federal-text law removes it in that province only.
  - Held text is served back to the date it is known to be the law: its start, or its latest dated amendment. Any
    undated amendment makes earlier dates unknown.
- Why: golden set 3 found the Hindu Marriage Act 2017 served in Sindh, and repealed laws served in provinces that
  had repealed them.
- Where: migrations 0095–0100; audit A17; commit bb49c29; tests/test_territorial_serving.py.

### D-045 · 2026-11-16 · Golden sets check their answers against the held text at every build
Area: evaluation · Status: standing
- Decision:
  - Each case's propositions carry patterns the provision text must match at build time.
  - A provincial copy of a federal code counts as equivalent only if its text is identical; a differing copy stops
    the build.
  - A tenth of cases are deliberately unanswerable.
- Why: a golden set that drifts from the corpus measures nothing. Punjab's copies of some codes do differ (Family
  Courts s.10, PPC s.500).
- Where: evals/golden (golden_common.py, build_set1–4); commits 88719df, ffdfd32; docs/10.

### D-046 · 2026-11-16 · Gilgit-Baltistan acquired from archived official captures
Area: corpus · Status: standing
- Decision: every PDF on the GB Assembly site returned 404, so its Acts were staged from Internet Archive captures
  of the official site, hash-checked, and preflighted. 27 text-layer Acts were landed and released.
- Where: commit 909b562; tools/acquire/stage_wayback.py.

### D-047 · 2026-11-17 · Catalogue year and kind are corrected from the law's own text
Area: schema · Status: standing
- Decision: a standing assertion of `year` or `kind` corrects the catalogue value after every replay. The ltree
  path keeps the catalogue values, so paths stay stable.
- Why: five laws carried the wrong year or kind (6688, 8846, 9067, 11379, 11382).
- Where: migration 0101; tools/evidence/catalogue-corrections-2026-11-17.sql.

### D-048 · 2026-11-17 · The pre-1947 rule applies to every kind of instrument
Area: serving · Status: standing
- Decision: a pre-independence archive text is never presumed in force, whatever its kind.
- Why: correcting doc 6688 to an Ordinance exposed 31 pre-1947 Ordinances that had escaped the rule.
- Where: `pre_independence_archive_text()` in tools/record_status.py.

### D-049 · 2026-11-17 · Repeals at unit level, and the units a whole repeal excepts
Area: serving · Status: standing
- Decision: a later law's repeal of a section, Part or Article drops that unit's subtree from the repeal date
  (0102). Units that a whole repeal expressly excepts stay served (0103), for example the Companies Ordinance 1984
  ss.282A–282N (Part VIIIA).
- Why: the Sindh Finance Act 1994 s.9 was still being served, and Part VIIIA was hidden by the Ordinance's repeal.
- Where: migrations 0102, 0103; audit A18; tools/record_provision_repeals.py (post-replay step 4a2).

### D-050 · 2026-11-17 · Two checked transfer formats for the database
Area: process · Status: standing
- Decision:
  - Logical: `./nz export` / `./nz restore`. The restore checks the sha256, the dump's database name and the corpus
    signature, and runs ANALYZE before the first view refresh.
  - Byte-exact: `./nz export --physical` / `./nz restore --physical`.
- Why: partners need an exact database. A bare restore once silently loaded a September dump of the retired
  database, and a refresh without statistics hung for over 35 minutes.
- Where: infra/scripts/restore.sh; SETUP.md; docs/CORPUS-STATE-2026-11-17.md.

### D-051 · 2026-11-17 · Snapshot files are deleted only on the user's confirmation
Area: process · Status: standing
- Decision: the roughly 13 GB of old snapshot files on E: stay until the user confirms deletion. Archives that a
  prune batch names are kept outside rotation.
- Why: lost prune evidence cannot be recovered; the archives for prune batches 3 and 4 were already rotated away.
- Where: docs/CORPUS-STATE-2026-11-17.md "Storage".

## Mobile client, first slices (17 November 2026)

### D-052 · 2026-11-17 · The app reads law text only through `operative_provision`
Area: client · Status: standing
- Decision: `GET /v1/law/provisions/{id}/text?as_of&territory` returns the unit and its whole served subtree in
  printed order, capped at 400 nodes, with a `not_served` code when nothing is served. The unit is resolved first,
  and the view is queried with the id and path as values.
- Why: the September adapter read `provision_version` directly and would have shown repealed sections as current.
  Joining the view from a CTE took 47 s; querying with values takes about 10 ms.
- Where: nizam/storage/library_read.py; tests/test_library_api.py; docs/MOBILE-LIBRARY-PREVIEW.md.

### D-053 · 2026-11-17 · No backdrop blur in the app
Area: client · Status: standing
- Decision: glass panels are solid; no `BackdropFilter`.
- Why: it aborted Impeller's OpenGL ES raster thread, which phones without Vulkan use, and it cost an offscreen
  pass on every frame for an effect that was barely visible.
- Where: apps/mobile/lib/design/components.dart; docs/MOBILE-LIBRARY-PREVIEW.md.

### D-054 · 2026-11-17 · Status wording follows the evidence
Area: client · Status: standing
- Decision: a law in force only by the owner's presumption reads "Treated as in force". A recorded commencement
  reads "In force since <date>". Not-law outcomes are notices, never error styling. The status banner sits above the
  text.
- Why: doc 13; a presumption must not read as a verified fact.
- Where: apps/mobile/lib/domain/law_status.dart; design/status_banner.dart.

### D-055 · 2026-11-17 · Citations are rendered by the server, from database fields
Area: client · Status: standing
- Decision: `render_citation(title, year, kind, label)` builds forms like "Pakistan Penal Code, 1860, s. 302" or
  "…, Preamble". It returns nothing rather than guess. The client only displays it.
- Why: INV-1.
- Where: nizam/storage/library_read.py; tests/test_library_api.py.

### D-056 · 2026-11-17 · A law page lists its sections lazily, with prefetch
Area: client · Status: standing
- Decision: `/v1/law/instruments/{id}/sections` serves a cached index per (law, date, territory), 40 to a page. The
  client asks for the next page 15 rows before the end of what is loaded. Each card shows the name (a button), two
  lines of the section's words, and "Read more".
- Why: the owner asked for a list that never feels like loading. A warm page takes about 5 ms.
- Where: nizam/api/library.py; apps/mobile/lib/presentation/sections.dart.

### D-057 · 2026-11-17 · The popular-laws shelf names laws by document and checks their titles
Area: client · Status: standing
- Decision: 18 laws are named by document id together with a title pattern they must match. A document whose title
  has changed is dropped rather than shown under a wrong name.
- Where: nizam/api/collections.py.

### D-058 · 2026-11-17 · Reading modes change density and tools, never what is served
Area: client · Status: standing
- Decision: the Everyday, Student, Lawyer and Judge modes change text size, grouping, citations, page numbers and
  the Judge record panel only. A mode is a reading preference, not an identity, and it is not yet kept across
  restarts.
- Why: doc 13 §02 ("progressive disclosure, not information deletion"; "evidence density, not certainty").
  Persisting the mode needs a package that would force the Android toolchain upgrade (see D-061).
- Where: apps/mobile/lib/domain/reading_mode.dart.

### D-059 · 2026-11-17 · Catalogue search reads the serving snapshot with a trigram index
Area: serving · Status: standing
- Decision:
  - Search `mv_instrument_serving` behind a trigram index (0105; 0104's index on the base table is dropped).
  - Sort by title, ignoring a leading number, punctuation or "The".
  - Title-prefix matches first, amending laws last.
  - The catalogue therefore lists only laws in the snapshot. The 51 as-made Gazette texts are reached through their
    consolidated twin (D-029).
- Why: search took 0.9 s and now takes 6–8 ms. Urdu titles had sorted first.
- Where: migrations 0104, 0105; library_read.py `_instruments`; tests/test_historical_expression.py.

### D-060 · 2026-11-17 · The source's dash glyph is shown as a dash; stored text stays verbatim
Area: client · Status: standing
- Decision: the Pakistan Code PDFs' small double-dash glyph, which their text layer gives as two underscores
  ("committed by__"), is displayed as "—". Longer runs (blanks to fill in) are left alone. The database text is not
  changed.
- Why: checked on the PPC page image (p.30). The stored text is evidence and stays as extracted.
- Where: `printedDashes` in apps/mobile/lib/presentation/statute_text.dart; test/statute_text_test.dart.

### D-061 · 2026-11-17 · The Android toolchain stays pinned for now
Area: client · Status: standing
- Decision: Flutter 3.29 with Gradle 8.10; `url_launcher_android` pinned at 6.3.16. Release signing is not
  configured yet.
- Why: 6.3.18 needs AGP 8.12.1. The toolchain is upgraded in one deliberate step, not package by package.
- Where: apps/mobile/pubspec.yaml; docs/MOBILE-LIBRARY-PREVIEW.md.

## The Pakistan Penal Code repair (17 November 2026)

### D-062 · 2026-11-17 · The PPC's leaked footnotes are set aside, not hand-edited
Area: corpus · Status: standing
- Decision: the federal PPC (doc 4441) was repaired through the standard workflow:
  1. a hold row taking it out of release;
  2. a block-repair spec: 23 footnote blocks set aside, and two blocks re-read as the section text alone;
  3. a replay;
  4. a tree diff;
  5. the verifier chain;
  6. the post-replay sequence.
- Why: 23 footnote blocks had been read as body text. That gave five false sections (the false "70" held s.4's
  clauses (1)–(4)) and footnote wording inside about 30 sections, some mid-sentence. The diff proved that all 1,154
  removed words came from the footnote blocks and that nothing was added.
- Where: tools/evidence/hold-ppc-footnotes-2026-11-17.sql; .artifacts/recrawl-queue/specs/blockfix-4441.json.

### D-063 · 2026-11-17 · Chapters inserted by amendment open their own chapter
Area: corpus · Status: standing
- Decision: the reviewed-chapter-opener rule accepts the inserted-chapter print form ("2[CHAPTER VA",
  "1[CHAPTER XVI A]") only for blocks named on a page review. The label joins the letter to the numeral ("XVIA"),
  the form the Code itself prints for VA, IXA and XXA. The PPC's body starts at "CHAPTER I", so Chapter I and the
  Preamble are law text.
- Why: six inserted chapters were being read as the end of the section before them. The Code's opening page had
  been read as contents, so the Preamble was not served at all.
- Where: nizam/corpus/segment.py (rule `reviewed_chapter_opener`); tests/test_ppc_inserted_chapters.py;
  tools/evidence/hold-ppc-structure-2026-11-17.sql; specs/blockfix-4441c.json.

### D-064 · 2026-11-17 · A contents reading is repeated for a twin instrument by evidence file
Area: process · Status: standing
- Decision: when a replay rebuilds twin instruments and the re-attach tool refuses (one label names an entry in
  each twin), the standing reading of an unchanged page is recorded again for the twin by an evidence SQL file that
  cites the decision it repeats.
- Why: the page has not changed, and leaving the gap pending would block release.
- Where: tools/evidence/carry-ppc-362N-twin-2026-11-17.sql, carry-ppc-362N-pass2-2026-11-17.sql.

### D-065 · 2026-11-17 · The law page lists the preamble first and titles each chapter
Area: client · Status: standing
- Decision: the section index includes preambles, sorted first. A chapter group's title is its heading or, where
  the parser stored the printed title line as the chapter's own words, that short text ("Chapter V — OF ABETMENT").
- Why: 477 released laws carry a preamble numbered after their first section.
- Where: library_read.py `_section_index`; apps/mobile/lib/presentation/sections.dart.

### D-066 · 2026-11-17 · Every decision is recorded in this log
Area: process · Status: standing
- Decision: this file is the single log of decisions. CLAUDE.md requires an entry in the same change that makes
  any new decision.
- Why: the owner asked for a trace back through every design, corpus and linking decision.
- Where: docs/DECISION-LOG.md; CLAUDE.md "Decision log".

### D-067 · 2026-11-17 · The release baseline is re-signed at the full release
Area: process · Status: standing
- Decision: the released-count guard (post-replay step 2c) compares against claude-baseline-89, signed on 17 Nov at
  10,339 released, 0 blocked (git 909b562). The September baseline (claude-baseline-88) is kept, unchanged, as a
  record.
- Why: every one of the 587 rises the guard reported against claude-baseline-88 was a law released through the
  October–November landings, each under its own review. With the stale baseline the guard stopped every
  post-replay sequence, so the steps after it ran by hand and the guard protected nothing. Re-signed, it again
  stops a real undeclared rise; against baseline 89 it reports 0.
- Where: `tools/second_parser_release.py prepare --out .artifacts/release-work-2026-09-24/claude-baseline-89`;
  tools/released_count_guard.py picks the newest baseline. Baselines live under `.artifacts/` (not in git), so a
  restored copy on another machine has none until it signs its own (the guard exits 2).

### D-068 · 2026-11-17 · A preamble printed under an empty Part or Chapter heading comes first in the tree
Area: corpus · Status: standing
- Decision: segmenter rule `preamble_before_empty_division`. A top-level preamble moves ahead of the run of Part or
  Chapter headings printed just above it, when none of those divisions holds a unit read before the preamble and
  none repeats the kind and label of an earlier child of the root. Only sibling order changes.
- Replays, each under a recorded approval:
  - The `--release-diff` dry-run selects only laws whose rebuild differs from the released tree in ordinals and
    nothing else.
  - The PPC's pass was held, and its contents reading carried (D-064).
  - In two rounds (257, then 104), 252 laws' preambles moved: 148 in the first round, then 104 more once the
    repeated-label guard was narrowed to later occurrences only.
  - The proof query found every replaced tree equal to its successor on path, parent, kind, label, pages, first
    block, text and heading. 18,529 units were renumbered, the release stayed at 10,339, and the guard (D-067)
    reported 0 rises.
  - Misordered released laws fell from 283 to 44.
- Why: consolidated texts print "PART I PRELIMINARY" (the PPC: "CHAPTER I INTRODUCTION"), then the preamble, then
  section 1. The walk appended the preamble after the still-empty division, so in document order (`ordinal`)
  sections 1..n came before the preamble printed above them: 283 released laws, 21,359 units. D-065's figure of
  477 compared ordinals across different parents and overstated it. Paths come from labels, but a repeated sibling
  key takes its position (`pt_I_n1_1`), so moving past one would renumber a stored path (INV-4). The rule refuses
  those cases.
- Left as they were (44 laws):
  - laws whose misordering comes from block order (units on page 1 whose first block sorts before the preamble);
  - the few where a jumped division is a later occurrence of a repeated label;
  - 7 whose rebuild differs for reasons older than this rule (the same diff with the rule disabled).
- Where: nizam/corpus/segment.py `preamble_before_empty_division`; tests/test_preamble_order.py; the worker's
  `--release-diff` dry-run (nizam/workers/segment.py); tools/evidence/hold-ppc-preamble-order-2026-11-17.sql,
  carry-ppc-362N-pass3-2026-11-17.sql.

### D-069 · 2026-11-17 · The Constitution's body starts at its Preamble, and its Annex is its own unit
Area: corpus · Status: standing
- Decision: two page-read readings for the Constitution of 1973 (doc 4419, both observations of the one file) were
  recorded:
  1. a body start at the "PREAMBLE" head (`source_body_start_block` 772043, p17);
  2. an Annex opener at "1[ANNEX" (`source_division_openers`, kind `annexure`, label "ANNEX", p145).
- The law was held, replayed under a recorded approval, re-verified, and the full post-replay sequence ran. The tree
  now reads: the Preamble, then Parts I–XII, with the Annex (the Objectives Resolution) at the end of Part XII.
- Why:
  - The parser read pages 17–19 as contents. So the Preamble was not served, and Articles 1–6 stood outside Part I.
  - The Objectives Resolution's recital in the Annex had become the instrument's "Preamble". Its words ("Allah
    Almighty") are the Annex's; the Preamble's are "Almighty Allah".
  - The Annex head, printed with its insertion mark "1[", was read as the end of Article 280(8).
- Proof (`.artifacts/const_proof.py`), per observation:
  - 1,925 of 1,927 units are equal on kind, label, pages, first block, heading and text.
  - 24 units (Articles 1–6 and their clauses) changed path from `…s_1` to `…pt_I.s_1`, as the PPC's sections did
    under Chapter I (D-063). No stored citation used those paths; the golden sets cite by document and label.
  - Two units changed: the Preamble's text is now the Preamble's, and Article 280(8) no longer ends with the Annex
    head. Two units are new: Part I "INTRODUCTORY" and the Annex.
- Afterwards:
  - the guard (D-067) reported 10,339 → 10,339 with 0 rises;
  - audit 40/40;
  - golden sets 1–4 rebuilt with 0 problems (provision ids are regenerated by a replay).
- Where: tools/evidence/constitution-4419-2026-11-17/ (readings.json and the four page renders);
  tools/evidence/hold-constitution-structure-2026-11-17.sql.

### D-070 · 2026-11-17 · One page for the Constitution; units named as the law names them; the reader moves on
Area: API and client · Status: standing
- Decision:
  1. "Explore constitutional texts" opens one page (`/constitution`), not a title search. It shows:
     - the Constitution itself: its standing, a start at the Preamble, its Parts by printed title;
     - then the texts around it, grouped by how they relate: its amending Acts and Orders (newest first, each with
       its count of recorded `amends` edges), an earlier edition (shown only when the date falls in its historical
       window, 0064), the constitutional instruments before 1973, and the AJK Interim Constitution's amendments.
     Membership is pinned server-side by document id and title pattern (`nizam/api/collections.py`,
     `GET /v1/law/collections/constitution`), as the popular shelf is. Group keys are codes; the client words them.
  2. A constitution's numbered units are Articles. The segmenter stores them as `section`; the instrument's stored
     kind `constitution` decides the noun, in the rendered citation ("…, 1973, Art. 199") and in the client
     (`domain/law_units.dart`).
  3. A Part, Chapter, Schedule or Annex without a heading is captioned with its own short served words (≤120
     characters, read through `operative_provision` as at the date). This applies to the structure list and the
     reader's trail, extending D-065. It replaces the bare "Read this unit" cards.
  4. The reader shows the path to the unit (law › Part › Chapter) and the units either side in printed order
     (`GET /v1/law/provisions/{id}/neighbours`, from the cached section index). This is fetched beside the text, never
     in its way. Its status banner is compact only for in-force or presumed standing.
  5. The section index lists an annexure or appendix, as it lists a schedule.
  6. Lists scroll by drag from any pointer (`MaterialScrollBehavior.dragDevices`). The home shelf also has
     previous/next buttons.
- Why: the owner asked for the Constitution to open as the Constitution, with the related texts explained on one
  page. The law page called Articles "sections". The structure view showed untitled cards. The reader had no way
  forward but Back. The emulator's mouse and a laptop touchpad could not drag the sideways shelf.
- Measured, on the emulator, 18 Nov:
  - Build (our code) is inside 16.7 ms for most frames: home p90 15.7 ms, reader max 14 ms.
  - Raster through the emulator's GL translator is not: home p50 20 ms, reader 68 of 271 frames over.
  - The reader drew within budget on the same emulator on 17 Nov. On 18 Nov the emulator also restarted its system
    server and showed "System UI isn't responding", with 2 GB guest RAM and about 1.8 GB free on the host.
  - So the stutter is mainly the emulator; a phone measurement is still owed.
- Where: nizam/api/collections.py, library.py; nizam/storage/library_read.py; apps/mobile/lib/presentation/
  constitution.dart, reader.dart, discover.dart, popular.dart; apps/mobile/lib/domain/law_units.dart;
  tests/test_library_api.py; apps/mobile/test/law_units_test.dart; integration_test/scroll_perf_test.dart.

### D-071 · 2026-11-18 · Boundary evidence is never pruned; the lost rows are restored
Area: corpus · Status: standing
- Decision:
  1. A `segmentation_boundary_candidate`'s link to the instrument it was recorded against becomes optional
     (migration 0106). The retired-revision prune now severs that link instead of deleting the candidate and its
     adjudications.
  2. The 228 candidates that active expression manifests cite but the live tables had lost were restored from the
     prune's own archive records (`instrument_revision_archive_manifest.archived_record->'boundary_candidates'`).
     They came back as originally recorded: same ids, evidence and adjudications (226 decisions, all
     `confirmed_split`). Only `instrument_id` is NULL, because it named the pruned revision.
  3. Audit criterion A19: every candidate an active manifest cites is held.
- Why: post-replay step 2 refused 19 reviewed multi-expression documents ("need a recorded confirmed_split boundary
  candidate at their first span start").
  - The candidates were keyed to the instrument that was active when they were recorded. A replay retired that
    instrument, and the 11 Nov prune (batch f97cfaf2) deleted 226 candidates with it; the 9 Sep prune deleted 2.
  - That was decision evidence for 99 documents. The archive dump (sha256 37c93bd6…) holds the same rows.
- After the restore:
  - A19: 315 citations, 0 missing; audit 41/41.
  - Step 2 re-materialised 18 of the 19, as identical rebuilds; the release stayed at 10,339.
  - Document 4347 is refused. Its expression 3 would rebuild with item 1 read as a "Part 1"; the released tree (Part
    I, items 1–5) is the better one and stands. Logged as older drift.
- Where: infra/postgres/migrations/0106_boundary_candidate_survives_prune.sql; tools/prune_retired_instruments.sql;
  tools/evidence/restore-boundary-evidence-2026-11-18.sql; tools/audit/criteria.sql (A19).

### D-072 · 2026-11-18 · Gazette page heads are page furniture, not a Part of the law
Area: corpus · Status: standing
- Decision: segmenter rule `gazette_running_head` (`gazette_furniture()`), applied after the curation readings.
  - **Recognised as furniture:**
    - a Gazette running head: odd pages "PART I] THE GAZETTE OF PAKISTAN, EXTRA., JAN. 29, 2025 23", even pages
      "24 THE GAZETTE OF PAKISTAN, … [PART I";
    - the issue's own Part heading: "PART I" over "Acts, Ordinances, President's Orders and Regulations".
  - **Where it matches:** a head is matched as a whole line. A head broken over two or three lines counts only when
    it ends in the Gazette's date and page.
  - **What it does:** a block that is only a head takes role `running_header`. A head fused onto a block's first line
    is cut from the parser's copy. Extracted text is never altered.
- Why:
  - Read as law, the odd head opened a false "Part I": 2,765 false divisions in 398 released laws. On first pages it
    also swept the Gazette's front matter and the previous law's last lines into that Part.
  - That is why 15 laws numbered their Preamble after sections printed below it. The even head ran into clauses and
    sub-sections.
- Replay, per law, only on proof:
  - The `--release-tree-dump` dry-run of all 445 affected released documents gave 444 expressions, 385 of them
    differing.
  - `.artifacts/gz_proof.py` keys units by kind, label and first block. A law passes only if:
    - every unit is kept;
    - none is added;
    - every text change is exactly Gazette head words removed;
    - the only units gone are false divisions whose own words are head words or front matter printed before the
      law's first unit;
    - the law's whole word multiset is unchanged apart from those words.
  - 230 passed. Replayed under a recorded approval, 225 were replaced; the release gate refused 5 (7306, 6871, 6728,
    6218, 8317) for repeated labels their rebuild left, and they stand as released. Every replaced canonical tree
    equals its proved rebuild field for field (`.artifacts/gz_after.py`).
  - Afterwards: guard 10,339 → 10,339, audit 41/41, golden sets 0 problems.
- Not replayed (155 laws), each still exactly as released:
  - Removing the false Part lets other page clutter fall into the text: stray page numbers, column headings, OCR
    smudges. Or the items around it change kind (section ↔ clause).
  - Those need page-read repairs, law by law, not a rule.
- Preamble order: misordered laws fell from 44 to 38 (2512, 2772, 4910, 6641, 6702 and 7708 fixed).
- Where: nizam/corpus/segment.py (`gazette_furniture`, `_GAZETTE_HEAD`, `_GAZETTE_HEAD_JOINED`);
  tests/test_gazette_head.py; nizam/workers/segment.py `--release-tree-dump`; `.artifacts/gz_proof.py`,
  `gz_after.py`, `gz_replay_docs.txt`.

### D-075 · 2026-11-18 · Lists open with the laws the corpus relies on; search by subject; the API runs as a service
Area: L2/API/client · Status: standing
- Decision:
  1. **Reliance measure.** `tools/measure_law_citations.py` reads every released law's text once and counts, per
     law, how many other released laws cite it by title. A citation ends at a type word, or for "Code of …" opens
     with one. A year printed after the name, then the citing law's jurisdiction, then federal, choose between laws
     of one name; an ambiguous name is not counted, and self-citation is not counted. Recorded `legal_edge` links
     are added as `edges_in`. The result is stored whole in `law_citation_count` (migration 0107), keyed by
     (document, expression).
     - Measured 18 Nov: Constitution 2,218 laws, CrPC 1,486, PPC 1,160, CPC 953; 3,626 laws are cited at least once.
  2. **Ranked lists.** The catalogue orders by title rank, then reliance: laws citing it, plus 3 per law linked by
     an edge, with the editorial shelf on top. Browsing a jurisdiction or kind therefore opens with the laws practice
     turns on; federal Acts open with CrPC, PPC, CPC, Limitation, Companies, Stamp. The keyset cursor carries
     reliance. Each card shows "Cited in N laws". This is a measured signal: it orders lists and never decides law.
  3. **Search by subject.** `GET /v1/law/search` matches section headings and marginal notes (GIN index
     `provision_heading_fts`, 0107). It returns laws with their best-matching units, ranked by match, matches and
     reliance, current law first. With no jurisdiction chosen, a law reproduced in another code is shown once.
     "robbery" → PPC ss. 390, 392, 393. "bail" → CrPC ss. 496–498. A browse aid, not L3 retrieval; no answer is
     formed.
  4. **Library page.** One box for a title or a subject, suggested searches, one-tap jurisdiction and kind chips,
     subject results with their sections opening in the reader, and an honest note on the order.
  5. **The API as a service.** `./nz api [start|stop|status|restart]` runs the library API detached, logging to
     logs/api.log, and `./nz up` starts it. The app retries a refused or dropped connection twice, after 0.4 s and
     1.2 s. An offline screen re-asks every 5 s and opens by itself; it shows no retry button, since offline is an
     outcome (client rules).
- Why:
  - The owner asked for the laws people rely on to come first in jurisdiction, kind and topic lists, and for a
    subject search to find, say, the law punishing robbery before minor laws. Nizam holds no usage data and invents
    none; how often the rest of the law cites a law is evidence in the corpus itself.
  - "Not connected": the API ran only as a background command of a working session, so each restart or end of
    session refused the app's requests.
- Not done, and why:
  - **155 Gazette laws (D-072):** their rebuild moves words between units, mostly in tariff and tax tables; there is
    no single pattern. They need page reading.
  - **Three recital "preambles" (7036, 9638, 9881):** the form-text override is refused, rightly, outside an opened
    form or appendix. The form must first be opened from the page.
  - **The amendment Acts (D-074):** they need OCR, and by the owner's rule OCR laws are not landed.
- Where: infra/postgres/migrations/0107_law_citation_count.sql; tools/measure_law_citations.py;
  nizam/storage/library_read.py (`RELIANCE`, `subject_search`); nizam/api/library.py; nz (`api`);
  apps/mobile/lib/presentation/catalogue.dart; apps/mobile/lib/data/library_repository.dart (retry);
  apps/mobile/lib/design/components.dart (LoadFailure); tests/test_library_api.py.

### D-073 · 2026-11-18 · A preamble reads as its printed recitals
Area: client · Status: standing
- Decision: the reader breaks a preamble's served text into paragraphs where a recital opens: WHEREAS, AND
  WHEREAS, WHEREIN, NOW THEREFORE, So that, Conscious of, Do hereby, It is hereby enacted, and the like. A break
  happens only after a printed stop or at the start. The printed head "PREAMBLE" is not repeated under the title
  that already says Preamble. No other word is changed, added or dropped (`domain/law_units.dart`
  `preambleParagraphs`, tested).
- Why: the stored text of every unit joins its printed blocks with spaces (`Node.text`), so the Constitution's
  Preamble read as one block. Changing the join in the segmenter would change the stored text of every released law
  that has a preamble. The words are right; only their layout was lost.
- Where: apps/mobile/lib/domain/law_units.dart; apps/mobile/lib/presentation/statute_text.dart;
  apps/mobile/test/law_units_test.dart.

### D-074 · 2026-11-18 · The 23rd–27th Amendment Acts are not landed
Area: corpus · Status: standing for the 23rd and 24th; superseded by D-076 for the 25th, 26th and 27th
- Decision: none of the later constitutional amendment Acts is landed.
  - **23rd (2017):** the only official copy found is the Bill as passed by the National Assembly, not the Act.
  - **24th (2017):** no official copy was found.
  - **25th, 26th and 27th:** the official Gazette copies (na.gov.pk) are staged with their sha256 in
    E:/nizam-data/acquire/constitution-amendments-2026-11-18/. Each is a scan whose text layer is poor OCR: the 25th
    misreads the National Assembly seat table ("l6", "t73"), the 26th gives new Article "9A" as "94", and the 27th
    misreads its running heads and law text throughout ("Constiflrtional Cout").
- Why: landed text is served as the law. A misread article number or seat count is a wrong citation (INV-1). By
  the owner's rule a file that needs OCR is not landed, and in practice these do. The Constitution's consolidated
  text (doc 4419) already reads with all five amendments.
- Fetching: generic User-Agent; TLS verified with a bundle that adds each site's missing GoGetSSL intermediate,
  fetched from the AIA URL in its own certificate.
- Where: the staging folder above (staged.csv, preflight.csv). Next step: the OCR lane (memory: the Kaggle GPU
  route) and a proofread before landing.

### D-076 · 2026-11-18 · The 25th, 26th and 27th Amendment Acts are landed from a three-way reading
Area: corpus · Status: standing · Supersedes D-074 for these three Acts
- Decision: the 25th (doc 11385, Act XXXVII of 2018), 26th (doc 11384, Act XXVI of 2024) and 27th (doc 11383,
  Act XXXII of 2025) Amendment Acts are landed from their official Gazette scans and released. They make 10,342 laws,
  none held.
  - **Owner instruction.** For these three Acts only, use the Kaggle GPU and the best OCR available, and release
    them correctly. The general owner rule that laws needing OCR are not landed still stands, and the 23rd and 24th
    stay unlanded (D-074).
  - **Source.** National Assembly Secretariat uploads (na.gov.pk). The host is added to `ALLOWED_HOSTS` in
    `recover_acquisition.py`, fetched with TLS verified as in D-074. They are landed under scraper version
    recrawl-2026-11-18/1, then held with a review row until read.
  - **The reading (43 pages).** Every page was read from its 130-dpi render and recorded line for line as a page
    reading (curation patches: pinread → txgo). It was then checked two ways:
    - **Against the scan's own OCR layer, both directions** (`.artifacts/ocrdiff.py`). Every disagreement was an OCR
      garble ("Q XVI" for XXVI, "1864" for 186A, "10" for 40) or page furniture. No word the OCR prints is missing.
    - **Against a Qwen3-VL-8B reading on Kaggle** (2× T4, kernel amendvlm, 43 pages, `.artifacts/vlmcmp.py`).
      - 25th: 1 disagreement; 26th: 11; 27th: 11. Every one was settled against the image.
      - The model drops the Table's role column ("Member", "Members"), reads "(iiia)" as "iia", doubles "Court", and
        reads "; and" as "; end" where the glyph is damaged. Each time the reading was right.
    - The Surya OCR kernel could not run: on the current Kaggle image CMake cannot enable CUDA (the libcuda it finds
      is a Julia artifact).
  - **As printed.** The Act is recorded as the Gazette printed it, misprints included: "Majils-e-Shoora", "45,"
    for s.45, "Constitutiona Court", 175A's two "(b)" items and s.40's missing "(b)".
    - The 26th's page 16 is a corrigendum the National Assembly published separately. It is set aside as
      not the Act's text, and its wording is kept in full in the page's set-aside note. It reads "declines, a judge",
      "appointed" and "Majlis-e-Shoora" for the three printed words. The consolidated Constitution (doc 4419) carries
      the corrected text.
  - **Structure.** Text that an amending provision quotes into the Constitution stays in that provision; it never
    becomes a unit of the Act (`source_quoted_insertion_spans` and `source_no_cut_blocks`, both reviewed and
    page-anchored).
    - Covered: the 27th's new Chapter 1A (Articles 175B–175L, pp7–11); the substituted Articles 185, 189, 200 and 209;
      the 26th's Articles 191A, 202A and 209; and the 25th's Article 106(1A)–(1B) and 246(d).
    - Trees: 25th, Preamble and ss.1–9 (26 units); 26th, Preamble and ss.1–27 (43); 27th, Preamble and ss.1–56 (138).
  - **New rule `reviewed_comma_section_label`** (`source_comma_label_section_blocks`). A named page-read block
    opening "45, Amendment of Article 206 …" opens s.45, but only as the next number after the root's last section.
    Anything else fails closed. Registered in the worker merge, the recorder and the materialiser; tested
    (tests/test_comma_section_label.py). `blockfix.py` now also anchors a page whose only new content is reviewed
    overrides.
  - **Metadata.** The title-region recorders read the raw OCR layer, so they recorded the 27th's long title as "…
    lhe Ctm.stitution …" and missed the names, numbers and two assent dates. The values are recorded instead as
    page-read assertions (tools/evidence/amendment-acts-metadata-2026-11-18.sql), and the 27th's garbled long title is
    superseded. Assent and commencement ("at once"): 31 May 2018, 21 Oct 2024, 13 Nov 2025. All three are in force.
- Why: the owner asked for these three Acts. The Constitution page listed the amendments without them, although the
  consolidated Constitution's footnotes cite them. A three-way reading (page image, the scan's OCR, an independent
  vision model) is a stronger check than any single OCR engine. Every citation stays a database record (INV-1).
- Proof:
  - Release: 10,339 → 10,342 laws, the rise declared in the replay approval ("new released expression").
  - Leakscan clean; text gate 100% / 99.3% / 99.4%. The shortfall is rare words outside the vocabulary (riba,
    suo motu, mutatis mutandis).
  - Post-replay sequence; audit 41/41; golden sets 1–4, 0 problems; full test suite passes.
  - Serving: 10,291 laws served directly, 8,246 current.
  - Edges: the Constitution's footnotes now resolve 38 `amends` edges to the three Acts (27th 25, 26th 8, 25th 5).
- Where:
  - Readings and overrides: `.artifacts/recrawl-queue/specs/read-1138{3,4,5}.unpinned.txt` and `edits-1138{3,4,5}.json`.
  - Model reading: E:/nizam-data/ocr/kaggle/out-amendvlm.
  - Code and evidence: nizam/corpus/segment.py; nizam/workers/segment.py; tools/record_curation_patch.py;
    tools/materialize_multi_instrument.py; tools/recrawl/blockfix.py; docs/SEGMENTATION-PROFILES.md;
    tools/evidence/hold-amendment-acts-ocr-2026-11-18.sql; tools/evidence/amendment-acts-metadata-2026-11-18.sql.

### D-077 · 2026-11-18 · Heritage is Pakistan's places and the law that protects them; regions carry their culture
Area: L6/client · Status: standing
- Decision:
  1. **The Heritage tab** answers "what does the law say about heritage here?" region by region. It was a single
     illustration and three notes on the 1956, 1962 and 1973 constitutions.
     - `GET /v1/law/collections/heritage` (nizam/api/collections.py) lists, for each of the eight jurisdictions, the
       principal heritage laws the library holds, pinned by document id and title pattern. A replaced document drops
       out.
       - Federal: Antiquities Act 1975, National Fund for Cultural Heritage, Lok Virsa, National Archives.
       - Punjab: Antiquities Act, Special Premises, Walled City of Lahore Act and its Rules, Heritage Foundation.
       - Sindh: Cultural Heritage (Preservation) Act 1994. KP: Antiquities Act 2016.
       - Balochistan: Cultural Heritage Preservation Act 2010, Antiquities Act 2014, Archives Act 2014.
       - AJK: Antiquities Act 1986 and its 2001 amendment.
       - Islamabad Capital Territory lists the federal laws, which is what it is served (0095).
       - Gilgit-Baltistan holds none yet and says so; it never borrows another jurisdiction's law.
     - **Questions people bring to heritage law are answered only by opening units,** never by a summary. Each
       pairing was checked against the served text:
       - found an old object: s.5A and s.13A;
       - building near a monument: s.22;
       - repairing a protected building: s.20;
       - how a place is declared protected, and objecting: s.10 and s.11;
       - damage and signboards: s.19 and s.23;
       - export: s.26;
       - culture: Constitution Art. 28.
       - The units come from the law's served section index at as_of (INV-5); headings and citations are records
         (INV-1). Question keys are codes the client words (docs/13).
  2. **Culture across the app, as ornament doing semantic work (docs/12).** Each region has a landmark and a craft:

     | Region | Landmark | Craft |
     |---|---|---|
     | Federal | Minar-e-Pakistan | truck art |
     | Punjab | Badshahi Mosque | Multani blue pottery |
     | Sindh | Mohenjo-daro | ajrak and ralli |
     | KP | Takht-i-Bahi | lacquer and metal work |
     | Balochistan | Ziarat Residency | Balochi mirror embroidery |
     | Islamabad | Faisal Mosque | none |
     | AJK | Red Fort, Muzaffarabad | namda and chain stitch |
     | Gilgit-Baltistan | Baltit Fort | Hunza embroidery |

     - Each landmark is drawn as original vector art (design/heritage_art.dart) with one note, and each craft as a
       motif band.
     - They appear on the Heritage tab, the home page's jurisdiction tiles, the library's "Where" chips, and the
       Heritage tab icon. In each place they name a region; they do not decorate.
  3. **Every external fact is checked and linked.** Each note and craft line in domain/heritage.dart was verified on
     18 Nov 2026 against the source it links: UNESCO's inscriptions (1980, 1981, 1997), the Badshahi Mosque's
     completion in 1673, the Faisal Mosque (Vedat Dalokay; 1969 competition; completed 1986), the Ziarat Residency
     (1892; national monument), the Red Fort (c.1559–1646), Baltit Fort (AKTC; UNESCO Asia-Pacific award 2004), and
     Minar-e-Pakistan (1960–1968). Where sources were thin (AJK papier-mâché, a "national" designation for truck
     art), the claim was narrowed to what the source supports.
- Why: the owner asked what Heritage is, for it to be useful, and for Pakistan's buildings and culture from every
  region to run through the app without costing speed. Heritage law (antiquities, special premises, the Walled City)
  is in the corpus for every jurisdiction but GB, and practical questions such as "I found something while digging"
  have exact answers in it.
- Performance, by construction: no image assets and no network. Each landmark's paths are built once (a static
  cache in a 100 × 100 box) and scaled at paint; each drawing is behind a RepaintBoundary and never animates.
  Measured on the emulator (scroll_perf_test, segment `heritage`):
  - build p50 2.3 ms and p90 9.5 ms, against 3.5 and 11.7 ms for home;
  - raster p50 15.9 ms, against 15.0 ms for the text-only reader. The emulator's raster is over budget on every
    screen (D-070).
- Where: nizam/api/collections.py (HERITAGE_*), nizam/api/library.py (`/v1/law/collections/heritage`), tests/test_library_api.py;
  apps/mobile/lib/domain/heritage.dart, design/heritage_art.dart, presentation/heritage.dart, presentation/discover.dart,
  presentation/catalogue.dart, design/components.dart; apps/mobile/test/heritage_test.dart (goldens heritage.png,
  heritage_art.png, discover_tall.png); integration_test/scroll_perf_test.dart; docs/MOBILE-LIBRARY-PREVIEW.md.

### D-078 · 2026-11-18 · Each region's heritage questions are answered by its own law, read in its territory
Area: L6/client/corpus · Status: standing (closes the D-077 open question on per-region heritage questions)
- Decision:
  1. **Each region asks its own law.** `HeritageRegion.questions` replaces the page-wide `questions` list. A
     region's units are read from its own heritage law's section index at as_of AND in its territory
     (`section_index(..., territory=)`), so a label, or a law, not served there drops out (INV-5). Every pairing
     was read against the served text, section by section:

     | Region | Law (doc) | found object | build near | repair | declared | damage/signs | export | visit |
     |---|---|---|---|---|---|---|---|---|
     | Federal, ICT | Antiquities Act 1975 (3468) | 5A, 13A | 22 | 20 | 10, 11 | 19, 23 | 26 | 31 |
     | Punjab | its copy of the 1975 Act (3157) | 5-A, 13A | 22 | 20 | 10, 11 | 19, 23 | 26 | 31 |
     | Sindh | Cultural Heritage (Preservation) Act 1994 (1336) | 5 | 11 | none | 6, 7 | 19 | none | 18 |
     | KP | Antiquities Act 2016 (5133) | 10, 22, 61 | 55 | 16 | 15, 19 | 18, 24 | 66 | 54 |
     | Balochistan | Antiquities Act 2014 (4986) | 6, 15 | 24 | 22 | 11, 12 | 21, 25 | 28 | 33 |
     | AJK | Antiquities Act 1986 (10935) | 6 | 23 | 21 | 11, 12 | 20, 24 | 27 | 32 |

     - A region whose law has no section for a question does not ask it, and none borrows another region's law.
       Gilgit-Baltistan asks nothing.
     - "Can the public visit a protected site?" (`visit`) is new: every antiquities law here has a right-of-access
       section.
     - KP s.66 sends export to the federal laws, and the card shows it saying so.
     - The Constitution's Art. 28 is asked wherever the Constitution is served: the four provinces, ICT and federal.
       It is not asked in AJK or GB.
     - `HeritageUnit.preview` carries the section index's served opening words. The client quotes them where the
       source prints no heading (Balochistan's and AJK's units), so a card never shows only "s. 6".
  2. **Doc 1336 repaired: the contents runs one row behind its body.**
     - Defect: the Sindh Cultural Heritage (Preservation) Act, 1994 prints a bare "7." after s.6(1) (p3) and s.6(2)–(4)
       under it (p4). Contents row n therefore names body section n+1 from row 7. The released tree linked the rows by
       number, so every section from s.8 carried the heading of the section before it: s.19, the penalty, was headed
       "Overriding effect". The margin notes of ss.9–20 were also read into the close of the section above.
     - Repair: following the owner's standing delegation (decision-review-2026-11-18-delegated-1336 q1, q2; page renders
       p1, p3, p4, p8 read), the document was held with a truthful review row
       (tools/evidence/hold-1336-contents-offset-2026-11-18.sql) and pinned to `unreleased-v4`. It was then replayed
       with two reviewed readings: `source_contents_row_links`, which links rows 1–6 to ss.1–6 and rows 7–21 to ss.8–22
       (s.7 and s.11 print no note and take no row), and a `source_printed_headings` entry giving s.8 its full margin
       note (the contents row wraps, and its stored words stop at "of the").
     - Proved by dry run, then by tree diff and the served text:
       - 72 → 71 provisions, the only path removed being a false s.7(1) opened at "sub-section (1)" mid-sentence,
         whose words rejoin s.7(2);
       - 15 headings now match their printed side notes;
       - leakscan hits fell from 11 to 4.
     - Re-verified, released again (10,342), post-replay sequence run in full, census recorded, audit 41/41.
     - Residuals, left as served: s.8(1) still ends with its margin note, because the note and s.8(2)'s first words
       are one block and no reviewed rule cuts a note that opens a block. The Sindh running head inside ss.7, 9, 12
       and 17 belongs to the known 190-document class. s.22's note is in a full-width block.
  3. **A territorial repeal "as applicable to the extent of" its own province is read.**
     - The Balochistan Antiquities Act, 2014 s.41(1) repeals "The Antiquities Act, 1975 ... as applicable to the extent
       of the Province of Balochistan". The `as applicable to` branch of tools/record_territorial_repeals.py took
       "the extent of the Province of Balochistan" as the place and skipped the clause, so the federal Act was still
       served in Balochistan.
     - The branch now admits an optional "the extent of", as the `in its application to` branch already did.
       tests/test_territorial_repeal_clause.py covers the shapes that must not change.
     - One row is recorded (47 → 48). The federal Act now serves 0 sections in Balochistan.
     - KP's 2016 Act repeals KP's own 1997 Act, not the federal one; nothing is claimed for KP.
- Why: the owner asked for the D-077 open item to be done. A reader in Sindh or Balochistan asking "I found an old
  object" was shown the federal Act, which in Balochistan has been repealed since 2014. Pairing each region's own law
  exposed the doc 1336 heading shift, which every reader of that law saw. It is fixed at the source rather than
  hidden at the API.
- Where: nizam/api/collections.py (HERITAGE_QUESTIONS by region, HERITAGE_CONSTITUTION_QUESTIONS), nizam/api/library.py,
  tests/test_library_api.py, tools/record_territorial_repeals.py, tests/test_territorial_repeal_clause.py,
  tools/evidence/hold-1336-contents-offset-2026-11-18.sql, tools/evidence/heritage-2026-11-18/ (readings, builder);
  apps/mobile/lib/presentation/heritage.dart, domain/heritage.dart, test/heritage_test.dart (golden heritage.png).

### D-079 · 2026-11-18 · Crafts and makers per region, and the law that protects what Pakistan makes
Area: L6/client · Status: standing
- Decision:
  1. **Every region names its crafts and makers**: two or three each instead of one. Each craft has its own drawn
     motif, its town, and one line checked on 18 Nov 2026 against the source it links.

     | Region | Craft, motif and source |
     |---|---|
     | Federal | truck art |
     | Punjab | Multani blue pottery; Sialkot footballs (Dawn: match balls for the 2022 World Cup); Chiniot carved furniture (TDAP furniture report) |
     | Sindh | ajrak and ralli; Hala and Nasarpur kashi tiles and Hala lacquer (AIC "Clay Culture of Blue Kashi Tiles") |
     | KP | lacquer and metal work; Peshawari chappal (APP) |
     | Balochistan | Balochi embroidery; Balochi rugs |
     | Islamabad | Lok Virsa, the national institute of folk and traditional heritage, founded 1974, a keeper of crafts (its law is in the federal list) |
     | AJK | namda and chain stitch; Muzaffarabad walnut carving (Express Tribune) |
     | GB | Hunza embroidery; the Gilgiti cap (Pamir Times) |

     - Claims were narrowed where the sources disagreed or were thin:
       - the World Cup balls are thermo-bonded, so the line claims no hand-stitching;
       - "nating", the chappal's "six stages" and a GB cap day were dropped for want of a solid source;
       - a list of six registered GIs (it included Hyderabad bangles) came from an undated report and is not
         repeated.
     - Eight new motifs, the same static painters: football, jaali, Hala tile, chappal braid, rug lozenge, folk
       vessels, chinar leaf, wool cap. A test proves every craft's motif is its own.
  2. **"Protecting what Pakistan makes"** is the federal law a maker relies on:
     - **The laws:** the Geographical Indications (Registration and Protection) Act, 2020 (doc 3433), the Trade
       Marks Ordinance, 2001 (4338), the Registered Designs Ordinance, 2000 (2722) and the Copyright Ordinance,
       1962 (3896). They are pinned like the heritage laws (`HeritagePage.makers`).
     - **The questions,** answered by sections read against the served text:
       - a product known by its place: s.11 (the Federal Government holds Pakistan's GIs) and s.26;
       - the national GI logo: s.28;
       - goods sold under a false place name: ss.30 and 41;
       - a workshop's mark: Trade Marks ss.22 and 39;
       - a new pattern or shape: Designs ss.3 and 8;
       - who owns a painting, song or photograph: Copyright ss.10 and 13.
     - **One editorial fact,** sourced: Basmati rice was registered as Pakistan's first GI in January 2021
       (Dawn).
  3. **Culture in the smaller blocks**, each saying something:
     - a "From the regions" card on Home shows one craft a day, keyed to the reader's as_of date (no clock, no
       randomness), and opens its region (`/heritage?region=`);
     - the reader's jurisdiction line is led by the region's landmark (`Eyebrow(jurisdiction:)`).
     - Result lists are left lean.
- Why: the owner asked for culture "deeper": truck art, blue pottery, Sialkot footballs and the like, across the
  app, intelligently and without cost. Crafts become useful where they meet the law a maker actually uses, and the
  corpus holds all four federal IP laws.
- Performance, measured on the emulator on 18 Nov (two runs; the emulator was under host memory pressure and every
  screen ran slower than on the 17 Nov runs):
  - Heritage: build p50 3.1 ms, p90 13.2–13.9 ms; raster p50 18–19 ms.
  - Home: build p50 5.0 ms and p90 19.7 ms in the warm run (8.6 / 27.1 ms in the first, cold-launch run), against
    3.5 / 11.7 ms before.
  - Reader (unchanged code): build p50 1.9–2.1 ms; raster p50 19–21 ms, against 15 ms before.
  - Home's p90 rose a little more than the other screens'. Measuring it on a phone is part of the open frame-budget
    item.
- Where: nizam/api/collections.py (MAKER_LAWS, MAKER_QUESTIONS), nizam/api/library.py (HeritageMakers),
  tests/test_library_api.py, tools/generate_library_contract.py; apps/mobile/lib/domain/heritage.dart (crafts,
  craftOfDay, giFirst), design/heritage_art.dart, design/components.dart (Eyebrow), presentation/heritage.dart,
  presentation/discover.dart, presentation/reader.dart, main.dart; apps/mobile/test/heritage_test.dart and goldens.

### D-080 · 2026-11-18 · Printed margin headings repaired in four heritage laws; leading margin notes become a reviewed rule
Area: L1 corpus · Status: standing (closes the D-078 residuals and the "Heritage law: what remains" open item)
- Decision:
  1. **New reviewed rule `reviewed_leading_margin_note`** (`source_leading_margin_notes` [{block_id, note, label}]).
     A page-read margin note that a text layer set at the head of a law block leaves the text. It becomes the
     marginal note of the top-level section named by `label`, which must hold the block. The rule is data-gated in
     every profile and fails closed.
  2. **`reviewed_margin_note_pieces` is widened.** A note printed across a page break may have pieces on the next page
     in reading order. A piece may also be a law block whose head carried part of the note.
     - Released A/B: every released document whose readings use the pieces or printed-heading keys was dry-run.
     - 61 of 65 rebuilt identically. 4367 and 4497 are multi-instrument documents the plain segmenter refuses by
       design. 2491, 4702, 8743 and 9868 fail or differ identically on the committed code: pre-existing drift.
  3. **Four released laws repaired.** Each was held with a truthful review row, replayed with page-read readings
     (tools/evidence/heritage-2026-11-18/patch-{4788n,4986n,5133h,1336n}.json), re-verified and released again (10,342).
     - **4788,** Balochistan Cultural Heritage Preservation Act 2010. The notes stand in a table's left column, read
       line by line into the text. All 18 sections now carry the printed headings: 14 from pieces, 4 from notes at
       the head of their block.
     - **4986,** Balochistan Antiquities Act 2014. Pinned to unreleased-v4, whose margin rule heads 37 sections; the
       readings head ss.4, 14, 20, 24 and 41. Two notes run across a page break.
       - Three false sub-sections opened mid-sentence ("sub-section (1)", "(2) of section 18") are gone: 199 → 196
         provisions.
       - s.24 now reads "...shall be undertaken or executed..." without the note breaking the sentence.
     - **5133,** KP Antiquities Act 2016 s.10. It is now headed "Accidental discovery of antiquity to be reported to
       the Director." instead of the contents row "...Director.]" with the Code's bracket, and its (1) opens as a
       sub-section. Owner delegation decision-review-2026-11-18-delegated-5133 q1.
     - **1336** s.8(1) no longer ends with its margin note.
  4. **Every reading was made from the page renders:** 4788 pp1–5 and 7–10; 4986 pp4, 8, 10, 11 and 16; 5133 p11;
     1336 p4.
     - The release gate's field-by-field dry-run diff showed only note words leaving the text and the three false
       sub-sections removed.
     - The served text was read after release.
     - Post-replay sequence run, census recorded, audit 41/41.
- Why: the owner asked for the items left unfixed after D-078 to be fixed. A Balochistan reader saw every section of
  both laws without a heading, with margin words broken into the law's sentences.
- Where: nizam/corpus/segment.py (rule and widening), nizam/workers/segment.py, tools/record_curation_patch.py,
  tools/materialize_multi_instrument.py, tests/test_leading_margin_note.py, docs/SEGMENTATION-PROFILES.md,
  tools/evidence/hold-margin-notes-d080-2026-11-18.sql, tools/evidence/heritage-2026-11-18/.

### D-081 · 2026-11-18 · Craft medallions behind the pages, never behind law text
Area: client · Status: Superseded in part by D-082 (the medallion and flat bands; "never behind law text" stands)
- Decision:
  - The owner asked for blue pottery, truck art and embroidery as backdrops: in a top corner, behind buttons.
  - **Page corners:** `LibraryScaffold(backdrop:)` places a faint craft medallion (`CraftCorner`: two rings of the
    craft's motif round a centre unit, as a tile rosette or a painted wheel-boss is laid out) behind the page's top
    corner.
    - Discover: truck art.
    - Library: Multani blue pottery.
    - Heritage: the chosen region's own craft.
  - **The Constitution card:** a blue-pottery rosette behind its button, and a truck-art band along its foot.
  - **Home sections** are divided by an embroidered running-stitch rule with mirrors (`StitchRule`).
  - **No backdrop where the body is law text:** the reader, a law's page, the Constitution page. docs/12's rule that
    the reading surface stays plain holds.
- Performance: each medallion is painted once outside the scrolling body, behind a RepaintBoundary, and never animates.
  - Two emulator runs: Heritage build p50 2.5 ms; Home 3.9–6.1 ms (5.0 before); reader 1.6–2.3 ms.
  - All within the emulator's run-to-run spread.
- Where: apps/mobile/lib/design/heritage_art.dart (CraftCorner, StitchRule), design/components.dart,
  presentation/discover.dart, presentation/catalogue.dart, presentation/heritage.dart; goldens.

### D-082 · 2026-11-18 · The browsing pages are embroidered cloth; content lies on it
Area: client · Status: Superseded by D-084 (the whole-page cloth; the hem, the stitch rule and opaque tinted panels stand)
- Decision: the owner found D-081's medallion and flat motifs poor. They asked for the crafts to sit behind every
  overlay, button and text but above the backdrop, looking embroidered on the screen, with content still readable and
  tappable.
  - **The page is embroidered cloth.** `EmbroideredGround` covers the whole page of Discover (truck art), the
    Library (blue pottery) and Heritage (the chosen region's craft). It lies over the page colour and under every
    card, button and line of text.
    - Opacity is .26 in light mode and .22 in dark.
    - The Constitution card carries blue pottery on its pine.
  - **It is stitched, not printed.** design/embroidery.dart has three stitchworks: truck-art phool patti (satin
    petals on running-stitch vines), kashi (back-stitch stars round satin rosettes) and shisha (satin diamonds round
    mirrors in buttonhole stitch). Every thread is drawn with an under-shadow, its colour and a highlight.
  - **Borders and rules are embroidered too.** `EmbroideredBorder` (a satin zigzag with mirrors) hems the
    Constitution card, each landmark scene and the makers section. `StitchRule`, a double running stitch with
    mirrors, divides Home's sections.
  - **Readability:** every tinted panel (notices, craft rows, the craft of the day, the GI note) is laid opaque
    (`solidTint`), so the cloth runs under it, not through its text. Cards are opaque surfaces.
  - **The law pages carry no cloth** (D-081 holds).
- Performance: one tile is stitched once into an image (per stitchwork and pixel ratio) and the page is filled with
  a repeating image shader: one draw, outside the scrolling body, never animated. Emulator, 18 Nov:
  - Heritage build p50 2.9 ms, Home 5.0 ms, the unchanged reader 2.9 ms;
  - raster within the emulator's run-to-run spread.
- Where: apps/mobile/lib/design/embroidery.dart; design/components.dart (LibraryScaffold, solidTint),
  design/heritage_art.dart, presentation/discover.dart, presentation/heritage.dart; test/heritage_test.dart
  (golden embroidery.png, a review sheet at 3x).

### D-158 · 2026-11-26 · Judgment chunks are embedded in the GPU generation's space (Qwen3-Embedding-8B), beside their CPU vectors
Area: L2 storage / L3 retrieval (precedent) · Status: standing (results to be recorded when the runs are loaded)
- Decision: every judgment chunk also gets the GPU generation's vector (generation 2, Qwen3-Embedding-8B @1d8ad4ca,
  D-099), the space statute chunks already hold (chunk_embedding_gpu).
  - One generation per device stays shared by laws and judgments (D-121's rule for the CPU side), so one question
    vector searches both.
  - Why: for statutes, the 8B space lifted hybrid recall@50 from .76 to .96 and Urdu to 1.0 (D-099). Urdu
    precedent questions are the weak path on the CPU space (D-133, D-137).
- Storage: migration 0141 adds `judgment_chunk_embedding_gpu`. It holds a chunk id (`ON DELETE CASCADE`: a re-read
  rebuilds chunks with new ids, and their vectors go with them), the generation and `bits bit(4096)`. Its HNSW
  index is built by the loader after the first load.
- The run: `tools/judgment_embed8b_export.py` writes the chunks lacking a GPU vector (763,392 on 26 Nov) in
  embed_inputs.py's format, with the generation's dev questions.
  - The unchanged shard kernel (`embed8b_kernel.py`) runs 24 shards as four Kaggle runs, two per account.
  - `KG_BITS=1`, new: the kernel saves each shard as packed sign bits (512 B a row, not 8 KB). That is exactly
    what bit(4096) stores, so nothing kept is lost, and the download is about 390 MB, not 6.3 GB.
- The loader (`tools/load_judgment_embeddings_gpu.py`) refuses unless:
  - the shards verify (tools/kaggle/shards.py);
  - the runs are the active GPU generation's model, commit and template, and their dev questions reproduce its
    vectors (cosine ≥ 0.999);
  - every exported chunk that still exists and lacks a vector has exactly the passage text the run embedded,
    compared character for character.
  A chunk removed by a re-read during the run is skipped, and one made since is a later top-up. The rule is the
  statutes' "exactly the chunks lacking", made safe for a run that takes hours while judgments land.
- Audit A33: every row is of the active GPU generation, and once the table holds any row every judgment chunk has
  one.
- Search: `precedent.search` with a 4096-dimension encoder (the GPU host's service, or precomputed question vectors
  in evaluation) searches `judgment_chunk_embedding_gpu`. Until its vectors are loaded it searches the CPU space,
  and the trace says so; it is never passed off as the GPU path.
  - `evals/precedent_eval.py --gpu-vectors` replays 8B question vectors made on Kaggle (q8push), as the statute
    benchmark does.
- Where: infra/postgres/migrations/0141_judgment_chunk_embedding_gpu.sql; tools/judgment_embed8b_export.py;
  tools/load_judgment_embeddings_gpu.py; tools/kaggle/embed8b_kernel.py (`BITS`); tools/kaggle/kg.sh
  (`KG_BITS`); nizam/storage/judgment_read.py (`dense_paragraphs_gpu`); nizam/retrieval/precedent.py;
  evals/precedent_eval.py; tools/audit/criteria.sql (A33); tests/test_precedent_query.py.

### D-157 · 2026-11-26 · The Federal Shariat Court's judgments are landed from its own site; a seat letter after a slash is part of a case number
Area: L1 precedent (acquisition, courts, case identity) · Status: standing (D-139's "crawl every court's own site")
- Source: federalshariatcourt.gov.pk. Its robots.txt disallows only /wp-admin/. It publishes four lists, read by
  `data/fsc_judgments_scraper.py` at 3 s a request:
  - the Shariat petitions table (`shariatjudgment2.2.php`, 160 rows), each with its case number, parties,
    citation, decision date, author, the **law challenged** and the remarks;
  - its criminal appeals (392) and Shariat suo motu (2), from the public `judgments_api.php` its own pages call
    with an empty search;
  - its landmark page (21, mostly the petitions again).
  - Result: 569 distinct files, 538 fetched; the court's server answers 404 for 29 and timed out on 2.
  - The law challenged is kept as the court's own words, in the listing. It is the evidence a later
    `invalidated_by` reading starts from (docs/03b; PRECEDENT-MODEL §4.3, lawyer-verified only), never itself a
    ruling.
- The court: it was already recorded (0118, Art. 203C), and Art. 203GG's rule (authority_rule 6, 7) binds the High
  Courts and their subordinate courts on its Chapter 3A questions.
  - Migration 0142 adds its six case types as its headers and lists print them: Shariat Petition ("Sh.P."),
    Shariat Suo Moto, Criminal Appeal, Jail Criminal Appeal, Criminal Revision, Criminal Murder Reference. Case
    lines were observed on page 1 of 247 files (`fsc-case-forms.json`).
- **The case grammar reads a seat letter after a slash** ('Criminal Appeal No.01/K OF 2022'; Lahore's bail
  register 'Crl. Misc. No.853/B/2014'), as it read '-K' (D-128).
  - Measured over all 63,992 released case lines first: 106 read differently, all newly read (no year was read
    before), and **none that was read moves**. Three stay unread.
  - Parser /17; the 106 judgments were re-read with `--only` (LHC 95, IHC 6, SC 4, AJKHC 1).
- Parser /17 also names the court of a letter-spaced heading ("I N T H E F E D E R A L S H A R I A T C O U R T").
  The names are compared with the spaces taken out, only when such a run is printed and the plain match failed.
  - An OCR misreading ("COU~T", "FEDE~L") is not repaired. Those files are held: their text layer is an old OCR,
    and they wait for the OCR lane.
- Landed (`--court FSC --source-id pk-fsc-judgments`): 537 distinct files, **281 released**, 104 of them undated.
  - Held 137: 82 with a court name misread in an old OCR text layer, 35 with no JUDGMENT/ORDER heading, 15 at J3,
    5 unreadable.
  - Needs OCR: 98. Reprints, not landed: 15. Duplicates: 6.
- Every recorded court now has released judgments.
  - The golden set's last "court not held" case (P1-X04, FSC) is replaced by P1-I40, an answerable FSC question
    (the Riba judgment, Sh.P. 30-L of 1991, paras 46, 161, 140), kept in the test split as P1-I38 was.
  - The coverage-gap test now looks for any recorded court with no judgment.
  - P1-X06 ("before coverage") moves from 1 January 1995 to 1 January 1980: the FSC's judgments reach back to
    27 May 1981.
  - P1-X07, a second before-coverage case (1 June 1979), is added to the test split, so abstention is still
    measured on test (docs/10).
  - Open: a court the corpus does not record (a family court, a tribunal) is not yet a typed coverage gap.
- Where: data/fsc_judgments_scraper.py; infra/postgres/migrations/0142_fsc_case_types.sql;
  nizam/storage/case_key.py (`_ITEM`); nizam/corpus/judgment.py (/17, `_court`); tests/test_judgment_case.py,
  test_judgment_parse.py, test_precedent_query.py; evals/golden/build_precedent1.py, split-precedent-v1.json.

### D-156 · 2026-11-26 · The Islamabad High Court's judgments are landed from the court's own listing
Area: L1 precedent (acquisition, courts) · Status: standing (D-139's "crawl every court's own site")
- Source: mis.ihc.gov.pk lists the decisions the court marks "approved for reporting" and "important" through its own
  public JSON service, `ihc.asmx/srchDecisionClms`, by case year. There is no captcha and no login, and robots.txt
  is absent.
  - `data/ihc_judgments_scraper.py` read case years 1990–2026 at 3 s a request: 3,515 decisions. 3,437 files were
    fetched in two runs. Of the 78 not fetched, 47 are refused with an HTTP error and 31 loop on a redirect, at the
    server.
  - Kept from the listing: the court's own record (case number, bench, author, listed date, subject, section,
    citation identifiers, and the Supreme Court's later appeal status and result).
  - Never kept: the headnote fields `O_IHC_HEADNOTE` and `O_SC_HEADNOTE` (D-120).
- The court: it was already recorded (0118, Art. 198). Art. 201's high-court rule (authority_rule 4, 5) already
  reaches its subordinate courts in ICT.
  - Migration 0140 adds its 21 case types as its headers print them: `tools/observe_case_forms.py` over 1 in 3
    files, with the number found printed in 894 of 1,090 headers. The observer now also reads the listing's
    'Type-num-year' form.
  - Short forms never seen printed ("t r", "m r", "str") are not recorded.
- Parser /16 reads its "ANNOUNCED IN AN OPEN COURT ON 17.04.2023" line. The same form dated 25 undated Lahore
  judgments, which were re-read with `--only`.
  - The blank form ("Announced in the open Court on this ______ day of May 2025") dates nothing. It is how most of
    the court's uploaded copies close.
- Landed (`--court IHC --source-id pk-ihc-judgments`): 3,424 distinct files, and **2,736 released**, 1,243 of them
  undated and 1,237 marked approved for reporting.
  - Held: 370 (164 with no header or a misread one, e.g. "ISTAMABAD", "ISLAMABADHIGH"; 135 with no
    JUDGMENT/ORDER heading; 71 at J3).
  - Needs OCR: 291. Reprints, not landed: 18. Duplicates: 9.
  - Links: 26,598 statute citations and 2,973 case citations resolved in the new judgments. Privacy rebuilt: 1,888
    judgments with names withheld.
  - Released judgments in all: **63,992**, 14,164 undated.
- Checked against the court's listing: 2,685 of 2,743 judgments agree on case number (its digits) and year.
  - Most of the rest are files deciding connected cases (the header names one, the listing another), or an
    objection case numbered later as a writ petition.
  - A few are text-layer misreads ("2O13"). None is guessed.
- **The listing's date is not taken as a decision date.** It agrees with the printed date in 1,389 of 1,495 dated
  judgments, and 72 differ by more than a week, so it is not the date of decision. The 1,243 undated judgments stay
  undated under D-124; the listed date is kept in the listing.
- Golden set: P1-X02 ("the IHC is not held") is replaced by P1-I39, an answerable IHC question (W.P. 2904/2016,
  paras 13, 22), kept in dev as D-138 did.
  - Two test tripwires listing "the courts held" were rewritten as rules: the citation opens with its own court's
    name, and gold is never in a court the set declares not held.
- Chunks: 63,661 new judgment chunks are embedded on a Kaggle T4 (D-132, second account; the first was at its
  two-session limit), loaded with `--load`. The sweep found none missing.
- After: audit 54/54 pass; dev (35 answerable, with P1-I39) hit@10 .686, MRR@10 .42, recall@50 .738, leaks 0
  (`precedent-eval-dev-d156.json`).
- Where: data/ihc_judgments_scraper.py; infra/postgres/migrations/0140_ihc_case_types.sql;
  tools/observe_case_forms.py; nizam/corpus/judgment.py (/16); tests/test_judgment_parse.py,
  test_precedent_query.py, test_judgment_db.py, test_precedent_golden.py; evals/golden/build_precedent1.py,
  split-precedent-v1.json.

### D-155 · 2026-11-26 · A judgment "card" is not embedded: measured on dev, it does not help
Area: L3 retrieval (precedent) · Status: measured, not adopted
- The question: should a judgment's headers and titles be embedded, so that a judgment can be found by meaning as a
  whole and not only by its paragraphs?
  - The law side already does this. Every law chunk embeds its act title and heading path in its context prefix
    (D-098).
  - Judgment chunks embed their court and case line in their prefix (D-121). Parties are names and are not
    embedded.
- What was tried: one card per shown judgment (61,191), built from records only and with no names: court, case
  type, year (or "date not printed"), disposition, and the six laws it applies most with their four most-cited
  units. Each card was embedded with the CPU encoder (bge-m3 sign bits, 12.8 cards/s). Cards ranked by Hamming
  distance as a fourth RRF generator, voting at the judgment.
- Measured on dev (D-153 harness, 34 answerable cases):
  - hit@10 .588 → .559;
  - MRR@10 .334 → .315;
  - recall@50 .701 → .672;
  - p50 latency +540 ms.
  Seven cases moved, three of them down, and Urdu recall@50 fell .5 → 0. Test was not read.
- Why it fails: a card says what a judgment is about in a dozen words, and the questions ask what it holds. The
  laws a card names are already a generator, and a better one: the cited path reads them exactly.
- Kept: nothing in the schema. The prototype (`card_proto.py`, `card_eval.py`) and its vectors stay in
  /mnt/e/nizam-data/embed/cards/ (not released). The run is in evals/results/precedent-eval-dev-d155-card.json.

### D-154 · 2026-11-26 · For a forum, the judgments that bind it take one more vote in precedent search
Area: L3 retrieval (precedent) · Status: standing (the docs set no order by authority; this records one)
- Decision: when a precedent question is asked for a forum (`Subordinate(territory)` or a court), the fused
  candidates whose court binds that forum on `as_of` take one more reciprocal-rank vote, in their fused order
  (1/(60+n) for the n-th binding judgment).
  - Bindingness comes from the recorded rules (`authority.load`, Arts. 189, 201, 203, 203GG, A24), never from a
    court's name.
  - A persuasive judgment keeps its place, and none is removed: the same judgments come back, only reordered. The
    hit carries `binding` among its generators.
- Why: after the High Courts landed (D-138–D-148), the corpus held six times the judgments D-137 was measured on.
  Generic questions ("bail under 489-F", "a temporary injunction") then filled the first ten with other provinces'
  High Courts, ahead of the court whose rulings bind the reader. docs/PRECEDENT-MODEL §5 records which court binds
  which, and search had not used it.
- Measured on dev (D-153 harness):
  - hit@10 .588 → .676;
  - MRR@10 .334 → .415;
  - recall@10 .544 → .647;
  - recall@50 .701 → .730.
  Twelve cases improved and one fell: P1-F01, by design. A KP court's gold there is a Lahore judgment, persuasive
  for it, and binding Peshawar and Supreme Court judgments now come first; it stays within the first 50.
  - paragraph@10 fell .556 → .452, because the judgments that now enter the ten are found by a non-gold
    paragraph.
  - Leaks 0, p50 1.06 s.
- Test, scored once (21 answerable): hit@10 .667, MRR@10 .423, recall@10 .667, recall@50 .881, paragraph@10 .615,
  leaks 0.
  - D-137's reading was .65 / .371 / .625 / .90 / .75, on a sixth of today's corpus and 20 cases. It is not a paired
    comparison.
  - Provisional: the gold is a draft (A1/A2).
- Where: nizam/retrieval/precedent.py (`search`); tests/test_precedent_query.py;
  evals/results/precedent-eval-{dev,test}-d154.json (the dev baseline without the vote: -dev-d151.json).

### D-153 · 2026-11-26 · Precedent gold names the file read; a re-read is followed by its bytes
Area: evaluation (precedent golden set) · Status: standing
- Decision: a precedent gold unit's `judgmentDocumentId` names the file read when the gold was written. Both the
  builder (`evals/golden/precedent_common.py`) and the harness (`evals/precedent_eval.py`) resolve it through that
  document's sha256 to the judgment released now from the same bytes.
  - A gold paragraph is still found by its printed number and checked against its words, so a re-read can move an
    id but never what the gold says.
- Why: the D-146 re-read gave the gold judgments new documents. The harness then mapped every gold judgment to
  nothing, and the dev run of 26 Nov read hit@10 .18 (D-137's dev was .78). The loss was in the instrument, not the
  search.
- Done: `build_precedent1.py` was rebuilt at d7c1a94 with 0 problems and the same gold paragraphs. Some LHC gold
  judgments now carry the dates D-146 read.
  - Dev now reads hit@10 .588, MRR@10 .334, recall@50 .701 (`precedent-eval-dev-d151.json`). Below D-137's .78 on a
    sixth of the corpus: D-154 takes that up.
- Where: evals/golden/precedent_common.py (`_judgment`); evals/precedent_eval.py (`_doc_to_judgment`);
  evals/golden/golden-pk-v1-precedent1.draft.*.

### D-152 · 2026-11-26 · A paragraph number printed in Urdu digits is kept in Western digits
Area: L1 precedent (parsing) · Status: standing
- Decision: judgment parser /15 keeps a paragraph or footnote number printed in Extended Arabic-Indic or Arabic-Indic
  digits ('۱.', '۲.') as the number read, in Western digits ('1', '2').
  - The number is the one printed, so none is invented (INV-1).
  - Its form is the one every identifier takes, so "para 2" of the citation and of the stored row agree.
- Why: Python's `\d` reads Urdu digits, so parser /12 stored '۱'…'۷' as the printed numbers of one Lahore judgment
  (W.P. No.46741 of 2021, `2021LHC3320.pdf`). The test that numbers are digits 1–999 failed on it.
- Done: that one file was re-read with `--only`. Its earlier reading was retired, its 55 chunks re-embedded, and
  cases, reporter index, links and privacy were rebuilt. No released paragraph number is now outside Western digits.
- Where: nizam/corpus/judgment.py (PARSER /15); tests/test_judgment_parse.py.

### D-151 · 2026-11-26 · Law aliases, third sheet: 128 printed names read and tied to held laws
Area: L1 precedent (linking) · Status: standing (the D-134 process)
- Decision: the sheet `docs/alias-review/law-aliases-2026-11-26.csv` was read. It lists 181 printed law names that
  resolved to no held law, each seen in 3 or more judgments or 10 or more citations. For each, its forms, candidates
  and passages were read (decisions in `docs/alias-review/fill_2026-11-26.py`).
  - **128 aliases were loaded** (`law_alias`, 316 in all), and the loader verified each one. Examples:
    - SBCO / SBCA 1979 → Sindh Buildings Control Ordinance;
    - SCNS / Sindh CNS Act 2024;
    - SAA 2013 → Sindh Arms Act;
    - IPOP Act 2012;
    - "MSO 2001" → Pakistan Merchant Shipping Ordinance;
    - "DHA Order" → Pakistan Defence Officers Housing Authority Order 1980;
    - "Act IX of 1991" → Punjab Pre-emption Act 1991;
    - "ATC Act 1997" s.21-H → Anti-Terrorism Act 1997.
  - Each was decided from its passage. "MPO Ordinance" in Sindh judgments is the Maintenance of Public Order
    Ordinance (preventive detention), not the Motion Pictures Ordinance the resolver offered. "Sindh Tax Act, 1990"
    is the Sales Tax Act (the judgment speaks of FBR input-tax adjustment).
  - 53 were not aliased: not held 27, ambiguous 15, historical 7, foreign 2, not a law 2. Not held are the laws
    judgments cite that the corpus lacks: Sindh's own Land Revenue Act 1967, General Clauses Act, Maintenance of
    Public Order and Pure Food Ordinances 1960, Board of Revenue Act 1957, the federal CNS (Amendment) Acts 2022
    and 2024, the Azad Penal Code, and the AJK Civil Servants Act 1976. They are acquisition work, not aliases.
  - Two refusals by the loader were kept, never forced:
    - document 9361 holds three laws, so the KDA Order alias points at document 9246, which holds the Order alone;
    - SPP (REO) 2010's title search finds its amending Ordinance first, so it stays ambiguous.
- Why: D-134's process. An alias grows only from evidence a person reads.
- Where: docs/alias-review/law-aliases-2026-11-26.csv and fill_2026-11-26.py; law_alias.

### D-150 · 2026-11-26 · A law-report index from the court's own listing: reporter citations resolve to the case
Area: L1 precedent (linking, search) · Status: standing
- Decision: migration 0139 adds `reporter_citation`. Each row ties a reporter citation the Supreme Court publishes
  for its own judgment ('2026 SCMR 715', 'PLD 2016 SC 1', and the second series a cell may print) to that judgment
  and its lead case.
  - **Source:** the citation columns of its search listing (D-148) and of its "Last 25" listing (D-144).
  - **Builder:** `nizam.workers.reporter_index`. It rebuilds the table from the listings and the release.
  - **Key:** the judgment linker's own grammar and `judgment_linking.reporter_key`, with the court folded ('SC',
    'S.C.', 'Supreme Court' → SC), so the citing text and the listing agree by construction.
  - **One decision, several files:** a decision listed under several files (its short order and reasons, or connected
    cases decided together) keeps its citation when one claimant's case line covers every claimant's lead. Otherwise
    it is dropped, never guessed between: 53 dropped, 9 kept this way.
  - **Built on 26 Nov:** 2,195 citations (SCMR 1,601, PLD 554, …).
- **Linker /8:** a reporter citation resolves through the index to the case, and to its one decision where it has
  one, as a case-number citation does (D-125). Before this, all 174,657 reporter-style citations were 'not_held'.
- **Precedent search:** a question printing a reporter citation finds that case first, as a printed case number
  does (D-137).
- **Audit A32:** every row names a released judgment and a recorded case, every citation names one case, and one
  builder made the table.
- Identifiers only: no headnote or other reporter text is stored (D-120).
- Measured (relink /8, 26 Nov): 29,621 of 167,574 reporter citations in judgments now resolve to a case through
  the index. Before it, every one was 'not_held'. 2,065 distinct citations are indexed. Case citations resolved in
  all: 30,047 (426 by case number).
- Run order after a judgment landing: judgment_cases, then reporter_index, then judgment_links.
- Open: the court's own neutral citation ('2025 SCP 399', 3,815 rows) is not read by the grammar. It would key
  judgments citing it once they do.
- Where: infra/postgres/migrations/0139_reporter_citation.sql; nizam/workers/reporter_index.py;
  nizam/storage/judgment_linking.py; nizam/workers/judgment_links.py; nizam/retrieval/precedent.py;
  tools/audit/criteria.sql (A32); tests/test_precedent_query.py.

### D-149 · 2026-11-26 · A printed law name resolves by how well a title fits it, before the court's territory
Area: L3 retrieval / L1 linking (citations) · Status: standing (corrects D-128's ordering)
- Decision: `citations.resolve` searches laws whose title holds every printed word. For a name printed in a judgment
  or a question, with no code alias or reviewed alias, it now ranks the candidates by `name_fit` before the session's
  order (served, the court's territory, federal, reliance):
  1. the same name, once a province prefix, a year, plural endings and a one-word bracket (an acronym, "(ATA)")
     are set aside;
  2. the name as one run within the title ('Indian Limitation Act');
  3. its words in order with others between them;
  4. the words only somewhere. This is never a resolution.
  A bracket of two or more words is the law's own words, so it lends nothing to another name. 25 candidates are
  read, where 10 were before.
  A name printed as an acronym ("PEMRA Ordinance", "FIA Act", "OGRA Ordinance") is also read as the title's bracket
  acronym plus its kind. The fit is taken over both the short and the display title (`name_fit_any`). A plural is
  folded only for words longer than three letters ("Laws" → "Law", never "ss").
- Why: three wrong-law links were found on 26 Nov.
  - 48 Peshawar citations of "section 5 of the Limitation Act" had resolved to KP's School Bags (Limitation of
    Weight) Act 2020.
  - 12 AJK citations had resolved to an LLP adaptation Act.
  - 52 Sindh citations of "Sales Tax Act" had resolved to the Sindh Sales Tax on Services Act.
  The court's territory was preferred over the fit of the name. Retrieval's citation fast path is the same code, so
  a question asked with KP selected would have been misrouted too.
  - A first version of the rule refused acronym names and "Muslim Family Law Ordinance". The relink showed this, and
    the acronym and plural readings were added before the rule was kept.
- Measured: the golden citation set is unchanged (full 399 + 6 alternates of 406, the same one unresolved as on
  24 Nov; alias 100/100; bare 77/77; WRONG 0).
  - Every judgment was relinked under /8 on 26 Nov. Of 393,519 statute citations, 295,513 resolve, 24,426 name a
    law not held, and 79,586 are also linked to another copy. The privacy rebuild left 1,748 judgments with names
    withheld. A26, A29 and A30 pass.
- Where: nizam/storage/citations.py (`name_fit`, `name_fit_any`, `_fit_words`); nizam/storage/unit_search.py
  (`instrument_titles`); tests/test_name_fit.py; linker /8.

### D-148 · 2026-11-25 · The Supreme Court's judgment search is crawled in a visible browser with the owner present to answer any captcha
Area: L1 precedent (acquisition) · Status: standing (owner ruling; amends D-144's "open listing only")
- Decision: `data/scp_search_crawler.py` drives the search in a visible Chrome window on its own fresh profile, not
  the owner's. The owner is present, and if the site shows a captcha challenge, the owner answers it in that window.
  - Each search is the form's own submit, run in the owner's window.
  - Paging is the grid's own postback.
  - The script never solves, bypasses or replays a captcha token. The site's reCAPTCHA v3 scores the window as it
    would any visitor.
  - It runs one search per case year (2026 back to 1980) at 100 rows a page, 4 s apart. Every page is saved
    (`search/y<year>-p<n>.html`) and every row recorded with its judgment and upload dates (`search/rows.jsonl`).
  - Files neither archive holds are queued in the site archive's listing. They are downloaded by
    `data/scp_judgments_scraper.py` from the open `/Judgments/` folder and landed as D-144's were.
- Why: the owner ruled to crawl the search with a person answering any challenge. D-144 had read only the open "Last
  25" listing, which left the uploads of 7 Sep–3 Nov unreachable. The rows' judgment dates can also date Supreme
  Court judgments the archive holds as undated (D-124), as records, never guesses.
- Unchanged: robots.txt says ai-train=no, so this text never enters a training set (D-144). No headnote or reporter
  text is used (D-120).
- As run on 25 Nov:
  - The search lists 3,865 files across case years 1980–2026. No case is listed for 1980–1992 except one in 1993
    and six in 1996. No challenge appeared.
  - 3,737 of the listed files were already held: 3,711 in the September archive and 26 in the site archive.
  - Of the 128 new files, 124 were downloaded.
  - The file with a space and an "&" in its name ("ICA3 &4-2011DT2011.pdf") gets 400 from the server however its
    name is encoded. Three Const.P. 42 files on the September archive's retry list return 404.
  - 79 new Supreme Court judgments were released, 8 of them undated; 5 files need OCR and 2 are held.
  - Of 136 parsed files, 133 have a case number that agrees with the court's listing. One differs: CMAs 3685-3686
    of 2012 in HRC 7734-G of 2009, keyed to the HRC case, as the archive's other copy of that order is. Two listing
    rows print no number to compare.
  - The listing's judgment dates cover only 4 of the 316 undated Supreme Court judgments, so no "listed date" basis
    is added.
- Crawler lessons:
  - At 100 rows a page, responses were cut short, so it pages at 50.
  - An Urdu-version row's tagline can link the main judgment, so links inside taglines are not rows.
  - The refusal message sits hidden in every page, so only a visible one counts. The owner confirmed the stalls on
    25 Nov were the connection, not the site.
- Where: data/scp_search_crawler.py; E:/nizam-data/acquire/scp/search/.

### D-147 · 2026-11-25 · Sub-section (1) opens in GB Order ss.7, 51, 77 and 91, closing D-145's open item; rule F's third form
Area: L1 corpus (released-law repair) · Status: standing (closes D-145's open item)
- Decision: the four GB Order 2018 sections (doc 11635) that D-145 left open are read and recorded, and the law
  replayed with no law text changed: 742 → 746 provisions.
- Two shapes, each read on its page (renders under .artifacts/first-subsection-2026-11-25/renders):
  - **ss.7 and 91:** the heading runs to a second line, where the dash and (1) are printed and the sub-section's
    words follow ("void.-(1) Any law ..."). Rule F's first form already cuts that block; it had not been read.
  - **ss.51 and 77:** (1) closes the heading's line, and the words open the next line ("... circumstances.- (1)" /
    "The seat of a member ..."). **Rule F gains a third form** (`_K6_HYPHEN_SUB_AT_END`), tried only where neither
    earlier form finds a place: it cuts after the dash when (1) is the block's last text.
- s.51's clauses (a)–(e) now sit under s.51(1), where the page prints them; before, they hung on s.51 beside
  (2)–(4).
- Recorder trap: a reading whose locator line is the same text as an earlier patch's locator on that page is
  refused as "already recorded", even when it carries a different rule. Page 52's reading is therefore located by
  the heading's first line.
- Tests: tests/test_k6_rules_fg.py covers the second form (D-145) and the third.
- Where: nizam/corpus/segment.py; tools/evidence/first-subsection-2026-11-25/build_readings_d147.py and
  readings-d147.json.

### D-146 · 2026-11-25 · Parsers /13 and /14: orders with no heading open at their date line or wrapped column header; Sindh's header decision date; every court's undated judgments re-read
Area: L1 precedent (PRECEDENT-MODEL §3) · Status: standing
- Decision: three reads are added and one is refused.
  - **/13 `Order Dated:` opens an order that prints no heading.** A line that is only "Order Dated: <date>" (the GB
    Supreme Appellate Court's bench orders; some High Court orders) closes the header. The order begins after it, as
    an order of the court, and the line dates it (date_of_order, the /12 rule). It applies only where no heading,
    column header or author line is found. A date inside a sentence ("the impugned order dated ...") is never such a
    line.
  - **/13 the order sheet's column header, wrapped or misread.** "Date Order with signature of" / "Hon'ble Judge" over
    two lines; "srgnature"; "Judge" cut to "JUDG" or "jud" (Sindh).
  - **/13 author lines and dates:** "ZULFIQAR ALI SANGI, J;-" is an author line, but only as "J;-": a Sindh bench line
    prints "Muhammad Saleem Jessar J; Adnan-ul-Karim Memon, J;". A soft hyphen (U+00AD) separates a date's parts in
    some GB files ("08­06­2010").
  - **/14 Sindh's header line "Date of hearing & decision:" / "Date of hearing and Judgment:"** dates the judgment
    (date_of_decision), as "Date of hearing and order" already did. A hearing date alone never does.
  - **Refused: "FAZAL SUBHAN. J.-"** (a stop between the name and J). The Peshawar files that print it are OCR'd text
    layers, and their case lines read wrong: 17 of 21 differed from the case their own file name gives ("W.P No.
    79-A of 2015" read as 79-N/2019). They stay held for the OCR lane. A file name is evidence, never a source of
    the case key.
- **Re-read and landed (25 Nov):**
  - **/12 over every court's undated judgments** (8,488 files; Lahore was re-read under D-142): 88 gained a date
    (Sindh 68, Peshawar 16, the Supreme Court 4), and 2 Peshawar files were caught as law-report reprints. The AJK
    and GB courts' undated judgments print no decision date: a blank day ("__.01.2017", "-----1.2019") or only a hearing.
    They stay undated, bounded by the hearing or the case year (D-124).
  - **/13 over the 1,658 files held for 'no heading'**: 341 released (Sindh 248, GB SAC 86, Lahore 6, Peshawar 1), 6
    as duplicates of judgments already held. The rest stay held: separate opinions issued as files of their own (the
    Supreme Court), orders with no marker where their header ends, and OCR'd scans.
  - **/14 over the 632 undated files printing the line:** 602 Sindh judgments and 1 Lahore judgment dated.
  - **Released: 61,177 judgments** (60,826 before, plus 22 from the Supreme Court's site, D-144), **12,938 undated**.
- Why: these were the gaps D-142 left open. Each rule was read against a sample of the files it would release, before
  applying it.
- Open: undated Lahore (4,996) and Sindh (6,267) judgments, other header forms (a label and its date in separate
  columns), and the OCR lane for Peshawar's text-layer scans.
- Where: nizam/corpus/judgment.py (`_ORDER_DATED` as an opener, `_ORDER_COLUMNS`, `_AUTHOR`, `_D_NUM`/`DATE`,
  `_DATE_OF_DECISION`); tests/test_judgment_parse.py.

### D-145 · 2026-11-25 · Sub-Article (1) printed on its heading's line opens in the AJK Interim Constitution and the GB Order
Area: L1 corpus (released-law repair) · Status: standing (closes D-140's open item)
- Decision: where an Article or section prints its number, its heading closed by a dash, and "(1)" on one line, the
  reviewed rule `reviewed_hyphen_first_subsection` (rule F, doc 4450) cuts the block after the dash so that sub-Article
  (1) opens. Recorded by 30 page readings (tools/evidence/first-subsection-2026-11-25/), and both laws replayed and
  released again with no law text changed:
  - AJK Interim Constitution 1974 (doc 11875): 15 Articles (1, 5, 7, 12, 18, 19, 28, 30, 39, 42, 51, 51-A, 52, 53, 57);
    697 → 712 provisions.
  - GB Order 2018 (doc 11635): 17 sections; 725 → 742 provisions.
  - Clauses and provisos printed under (1) move into it: Art. 52(1)(a)–(b) had hung on Art. 52 itself, beside
    52(2)–(5); s.108(1)'s proviso had sat after s.108(4).
- **Rule F gains a second form**, tried only where its first finds no place, so a block it already cut keeps that
  cut. It accepts:
  - a note marker before or after (1) ("President.- 1[(1) There", "etc.- (1) 3[Subject", "Assembly.- 2[(1)] The");
  - a heading closed inside its amendment bracket ("quorum.-] (1) Subject");
  - a space before the dash, or an underscore for it ("Commission. – (1)There", "Jurisdiction._ (1) Without");
  - a line end anywhere in that run.
- Why: Art. 42(1), the AJK Supreme Court's own founding words, had no unit, so a citation of "Art. 42(1)" could resolve
  only to the whole Article (INV-4). Within each law it was mixed: 52 AJK Articles and 56 GB sections already had their
  (1).
- Open: GB ss.7, 51, 77 and 91 print the heading and "(1)" in one block and the sub-section's words in the next. The
  rule cuts within one block, so they are unchanged. Other laws may print the same shape; not surveyed. (Closed by
  D-147.)
- Note: both replays' recorded approval reasons read "D-144: …". That was the number before the Supreme Court crawl took
  it, and the reason is this entry. Afterwards, these were rebuilt:
  - the chunks: 16,589 re-cut and embedded on the CPU; the GPU vectors wait for the Kaggle run;
  - the law link tables;
  - judgment links pointing at retired provision ids: 8,606 judgments relinked, their law re-segmented here and in
    earlier replays;
  - 53 alias evidence passages, re-pointed.
- Where: nizam/corpus/segment.py (`_K6_HYPHEN_SUB_MARKED`); tools/evidence/first-subsection-2026-11-25/.

### D-144 · 2026-11-25 · The Supreme Court's own site is crawled through its open listing only; its text never enters a training set
Area: L1 precedent acquisition (D-139; PRECEDENT-MODEL §0, §7) · Status: standing
- Decision: the Supreme Court is crawled from what scp.gov.pk serves without a block
  (`data/scp_judgments_scraper.py`, surveyed 25 Nov 2026):
  - **www.supremecourt.gov.pk is refused.** It answers 403 to every path, robots.txt included (an Akamai denial).
    The court's site is www.scp.gov.pk.
  - **robots.txt** allows every path to a generic client and signals `search=yes, ai-train=no, use=reference`; it
    says nothing on ai-input. It disallows the named AI crawlers.
  - **The judgment search is not used.** /JudgmentsSearch is protected by reCAPTCHA, and a block is never
    circumvented (D-139). The September archive (`scp_judgments.zip`, 3,750 files) was gathered through that search
    with a captcha-solving browser extension. That route is not repeated.
  - **The open listing is /LatestJudgments**: the last 25 uploads, each row giving the case number, title, author
    judge, judgment date and upload date, and some a tagline. The crawler keeps every row it has ever seen
    (`listing.jsonl`), so running it regularly keeps the court current from now on.
  - **Files are fetched from /Judgments/<file>.pdf.** The September manifest's 16 failed files are served there under
    the same names. 12 were already held, 1 is fetched now, and 3 are gone (404: `const.p._42_*`).
  - The advocates' portal (portal.scp.gov.pk) needs a sign-in, and is not used.
- **Landed:** 26 new files (none already held), 22 judgments released, 4 of them undated, as printed. The gates held 3:
  - a file with no heading;
  - a header naming no court in its first lines;
  - a case line with no year (J3).
  1 is a scan for the OCR lane. The archive is `scp_site_judgments.zip` under source `pk-scp-judgments`.
- **Not reachable:** judgments uploaded between the September archive (7 Sep, 25 from 2026) and the current listing
  (the earliest upload in it is 3 Nov). The listing shows only the last 25 and the search is behind reCAPTCHA. Owner
  question: ask the court for access, or accept the gap.
- **ai-train=no is kept.** This court's text is searched, quoted and cited (search=yes, use=reference), but never put
  into a training or fine-tuning set. That includes the reranker fine-tuning ADR-2 plans: Supreme Court passages may
  be scored as evaluation gold, never trained on. Training data built later must filter on court SC (and
  `pk-scp-judgments`).
- Why: D-139's owner ruling covers the AI opt-out for search. The captcha and the training signal are lines the ruling
  did not cross.
- Where: data/scp_judgments_scraper.py; /mnt/e/nizam-data/scp_site_judgments.zip.

### D-143 · 2026-11-25 · The Government of Gilgit-Baltistan Order 2018 is repaired from page readings
Area: L1 corpus (released-law repair) · Status: standing (closes D-141's open item)
- Decision: the GB Order 2018 (document 11635, observation 15449, released with the D-113 GB drop) is re-segmented
  with 86 page readings (tools/evidence/gb-order-2026-11-25/build_readings.py) and released again: 725 provisions
  (723 before), 122 sections, S7 0. The GB courts' words (D-141) are still found (A24).
  - **82 folios set aside.** Each page prints its own number at its foot, and the text layer read it into the
    sentence crossing the page ("If in respect of any financial year it is found- 37"; also in s.75's Explanation
    and s.84(10)(c)). Test: the block is only the page's number, its lowest block, in the bottom quarter, inside a
    provision.
  - **The false Article 78 removed.** The wrapped line "Article 78 of the Constitution of Islamic Republic of Pakistan:"
    ends s.70(5)'s sentence (reviewed_text_unit), and its proviso ("Provided that the Federal Government shall provide
    funds to the Council") is s.70(5)'s. "78 GB Order" now resolves to s.78 alone.
  - **Parts IV and XI opened.** "PART. IV-THE GOVERNMENT" and "PART. XI-THE JUDICATURE" print a stop after PART, which
    the reviewed part opener now takes (only reviewed openers; D-140's quote rule beside it). ss.75–91 sit under Part
    XI, and s.74(3) ends at its own words.
  - **The Second Schedule opened** (reviewed_schedule_heading): it had been read into the First.
  - Left as printed: the copy prints no Part V heading (Part IV is followed by Part VI), and "CHAPTER" on page 4 with
    no number. No label is invented.
- Why: leakscan reported this law clean, yet it served page numbers inside the GB courts' own provisions and a false
  unit beside their binding rule. leakscan tests running heads, margin citations and notes, not folios or wrapped
  cross-references, which is open (a folio test would have found these).
- Where: nizam/corpus/segment.py (`_ro_label_rx` part: `part\.?`); tools/evidence/gb-order-2026-11-25/.

### D-142 · 2026-11-25 · The court sites' judgments are landed: AJK, GB, Lahore, Peshawar and Balochistan; parsers /11 and /12
Area: L1 precedent (PRECEDENT-MODEL §3, §7) · Status: standing (closes D-139's crawls)
- Decision: the archives D-139 crawled are landed through the ordinary gates.

  | Court | Files | Released (undated) | Held | OCR lane | Reprints |
  |---|---:|---:|---:|---:|---:|
  | AJK Supreme Court | 958 | 673 (220) | 72 | 147 | — |
  | AJK High Court | 262 | 203 (5) | 28 | 30 | — |
  | GB Supreme Appellate Court | 748 | 556 (416) | 161 | 21 | — |
  | GB Chief Court | 154 | 22 (5) | 7 | 124 | — |
  | Lahore HC (new on its site) | 5,141 | +4,079 | 648 | 145 | 263 |
  | Peshawar HC (new on its site) | 144 | +92 | 38 | 14 | — |
  | Balochistan HC | 2,000 | +0 | — | — | all |

  - **60,826 judgments released** (55,229 before): Lahore 8,057, Peshawar 2,680.
  - **Balochistan's own site adds nothing.** Its per-judge pages serve 2,000 files byte-identical to the law-report
    archive already held (2,000 distinct sha256 in 4,001 source rows): PLC, P Cr. L J, MLD and CLC reprints, which
    D-120 does not land. It stays at 30.
  - Peshawar: 46 links on the court's own pages serve no PDF (truncated file names); they are a gap at the source.
  - Lahore's site also serves law-report reprints (263, caught by the D-120/D-138 gates). The /12 re-read caught 17
    more among Lahore judgments released before and retired them.
- **Case types and names (0138)**, as each court's own headers print them, folded as the parser folds. The GB
  Supreme Appellate Court's "under objection" registers are their own numbering series, so they are their own types.
  Court alias keys are folded too (0137): "Gilgit-Baltistan" is "gilgit baltistan".
- **Parser /11** (dates as these courts print them):
  - the AJK and GB seats (Muzaffarabad, Mirpur, Kotli, Rawalakot, Gilgit, Skardu) sign a judgment
    ("JUDGE / Mirpur, / 22.01.2018"); a blank day ("__.04.2019") stays undated;
  - GB: "Date of detail judgment", "Date of delivery of detail judgment", "Date of detail order", "Announced:-";
  - a line that is wholly an order's own date ("ORDER DATED: - 21.03.2019") dates it, last in the order of evidence
    and never against a conflict. "impugned order dated …" inside a sentence never does.
- **Parser /12** (a case number on evidence only):
  - **Defect found in released records.** 30 Sindh judgments printed "CP D101of 2012" (register letter and "of"
    glued), and the year 2012 was taken as the case number. "CRIMINAL APPEAL UNDER SECTION 417 CR.P.C" (GB Chief
    Court) gave case number 417. "Criminal Appeal N~2019" gave 2019.
  - The shared case grammar (storage/case_key.py) now reads an upper-case register letter glued to its digits, so
    the judgment row and its case key still agree (D-138). A number with no "No.", no year and no reading by that
    grammar is no case number: J3 holds it.
  - The 285 released judgments with no case year were re-read: Sindh's 30 now read D-101 of 2012, and the
    section-number and garbled readings are held.
  - Lahore's "Dates of hearing" (plural) bounds an undated judgment from below, and "Announced in open Court today
    i.e. 02.02.2011" dates it. Every undated Lahore judgment was re-read (5,066).
- Open:
  - **Headingless bench orders** (court line, case line, "PRESENT:-" with counsel, then the order and the signatures,
    no "ORDER" heading and no author line) are held: about 1 GB Supreme Appellate Court file in 9, and many of
    Lahore's 356 such holds. Taking them needs a header-end rule.
  - Many GB and Lahore judgments print only a hearing date. They are released undated with the hearing as their
    lower bound (D-124), never guessed.
  - Undated judgments of the other courts, read before /12, have not been re-read for its plural-hearing and
    "today i.e." forms.
  - The 16,557 law chunks re-cut by post-replay step 2 (multi-expression laws get new ids on every run) and the new
    judgment chunks wait for the one Kaggle run (A27, and A21/A22 for the GPU space).
- Where: migration 0138; nizam/corpus/judgment.py (/11, /12); nizam/storage/case_key.py (`_LEAD`);
  tests/test_judgment_parse.py, tests/test_judgment_case.py; E:/nizam-data/acquire/work/ (land, re-read lists, logs).

### D-141 · 2026-11-25 · The AJK and GB courts are recorded; every binding rule names the territories its words reach
Area: L2 precedent data (PRECEDENT-MODEL §1, §1.4) · Status: standing
- Decision: four courts join the registry (migration 0137), each resting on words in a released law (A24):
  - **AJKSC**, the Supreme Court of Azad Jammu and Kashmir (AJK Interim Constitution 1974 Art. 42, observation 15688,
    released D-140) and **AJKHC**, the High Court of Azad Jammu and Kashmir (Art. 43);
  - **GBSAC**, the Gilgit-Baltistan Supreme Appellate Court (Government of Gilgit-Baltistan Order 2018 s.75,
    observation 15449) and **GBCC**, the Gilgit-Baltistan Chief Court (s.84).
  - D-139 said the GB Order was "to acquire". It was already released (landed with the D-113 GB drop); the GB
    Government portal's copy staged today has the same sha256 as the held file.
- **Binding rules** (`authority_rule`, basis `dated_text`, from the day each text is served: AJK 12 May 2026, the
  archived copy's capture; GB 12 Sep 2026):
  - AJK Art. 42-B: the Supreme Court binds "all other Courts in Azad Jammu and Kashmir"; Art. 44-B: the High Court
    binds "all courts subordinate to it", subject to Art. 42-B.
  - GB s.78: the Supreme Appellate Court binds "all other Courts in the Gilgit-Baltistan"; s.88: the Chief Court binds
    "all Courts subordinate to it", printed "Subject to Section 60" (likely a misprint for s.78; quoted as printed).
  - Neither text prints a superintendence clause ("supervise and control"), so no `court_superintendence` row is
    seeded for ajk or gb. Which High Court a subordinate court answers to is then unrecorded, and "courts subordinate
    to it" answers NotRecorded there. A rule reaching "all other courts in" the territory needs no such record.
- **Each rule now records the territories its words reach** (`authority_rule.territories`). Before this, the resolver
  read "all other courts" as every court in the registry. Seeding the AJK and GB courts would have made a Supreme
  Court of Pakistan decision "binding" on the AJK courts, an AJK Supreme Court decision binding on the Lahore High
  Court, and Art. 201 ("any decision of a High Court") a rule for the AJK High Court.
  - 0118's rules print "in Pakistan" (Arts. 189, 201, 203GG). They reach `fed` (the federation's own courts) and the
    territories Art. 1(2)(a)–(b) names: the four Provinces and the Islamabad Capital Territory.
  - The AJK rules reach `ajk`; the GB rules reach `gb`.
  - A rule speaks only for deciding courts inside its reach (a class rule included). A receiving court outside every
    applicable rule's reach is **NotRecorded**, with the reason, never NotBinding. Whether an AJK or GB court is a
    "court in Pakistan" under Art. 1(2)(c) is a legal question no record in the corpus answers.
- Why: courts are data and bindingness is a dated rule read from the text (D-116). A rule's printed place is part of
  its words; reading it as everywhere was the silent default the registry could no longer carry.
- Found: the GB Order 2018 as released had defects leakscan does not catch:
  - page numbers (folios) in 57 provisions, including s.75's Explanation and s.84(10)(c);
  - a wrapped cross-reference read as a unit `art_78` beside s.78;
  - Part XI's heading ("PART. XI-THE JUDICATURE") swallowed into s.74(3), so ss.75–91 sat under Part X.
  Its court rows quote clean words and cite by observation and label, so the repair replay kept them. Repaired the
  same day (D-143).
- Where: migration 0137; nizam/storage/authority.py (`Rule.territories`, the reach test, superintendence only for
  `courts_subordinate_to_deciding`); tests/test_authority.py.

### D-140 · 2026-11-25 · The AJK Interim Constitution 1974 is landed and released; a provision's own numbered paragraphs are rebuilt from a reviewed reading
Area: L1 corpus (docs/02 §5; segmenter rules) · Status: standing
- Decision: the AJK Interim Constitution (staged D-096) is landed (observation 15688, document 11875) and released:
  97 Articles (1–59 and 38 lettered), 697 provisions, five Schedules, S7 33 → 0, leakscan clean.
- **Why it was blocked.** Art. 4(4) "The Rights" prints its 24 rights as paragraphs "1. Security of person.-" …
  "24. Preservation of language, script and culture.-", indented one step (x0 216) from the Articles (x0 144), in the
  same "N. Heading.-" grammar. The law prints no contents page with a text layer (pages 1–11 are scans) to compare
  headings against. So the walk read right 5 as the section after Article 4, rights 6–24 as Articles 6–24, and the
  real Articles 5–24 as clauses: 33 repeated labels, every right misfiled.
- **New reviewed rule `reviewed_paragraph_run`** (key `source_paragraph_runs`): a reading names the owner (sub-Article
  (4) of Article 4), the run's openers and every block of the run, in reading order.
  - The walk never sees those blocks, so the real Articles follow Article 4 in sequence.
  - The run is rebuilt under its owner: one clause per opener, with its "(1)" sub-paragraphs, "(a)" and "(i)" items,
    provisos (an open proviso takes the lettered items after it) and explanations nested inside it. Unmarked blocks
    continue the deepest open node. As the walk does for a law without contents, the leading amendment marker is not
    kept and the heading stays in the text.
  - Data-gated, so it is inert without a reading. Fail-closed: an opener out of sequence, an unnamed opener inside
    the run, a wrong owner, or a block that is not body text refuses the parse.
  - Known to the recorder, the worker merge and the multi-instrument dry run (the key-registry tests pin this).
- **The reviewed part opener takes a part heading printed in quotes** ("‘PART-A’", the Third Schedule); its closing
  quote is not part of the heading. Only reviewed openers are affected; no recorded patch's prefix starts with a
  quote.
- **110 page readings** (tools/evidence/ajk-ic-2026-11-25/build_readings.py, renders and sha256 in each):
  - the paragraph run;
  - ten amendment footnotes the parser read as clauses ("1. Subs. by the (Thirteenth Amdt.) Act, 2018", at the
    Articles' margin below each page's rule);
  - 104 page numbers read into the law's text, each the page minus 11 and the lowest block of its page. Their tops
    sit at 79.8% of an A4 page, so ajk_folio_patch.py's 80% line, made for the AJK Code's letter pages, would have
    missed them;
  - the Third, Fourth and Fifth Schedule headings printed behind their amendment marker ("1[THIRD SCHEDULE");
  - Article 30-A, printed with no stop after its number; and the Third Schedule's quoted Parts A and B.
- Found and left open:
  - Where a heading runs into "(1)" with no space ("Supreme Court of Azad Jammu and Kashmir.-(1) There shall be"),
    sub-Article (1) stays in the Article's own text (13 Articles). The text is whole; only "Art. 42(1)" is not
    addressable alone. This is the segmenter's existing inline-split grammar, rarer in Pakistan's Constitution (1 of
    8), and a corpus-wide question.
  - Post-replay step 2 refused to re-materialise document 4347 expression 3 (5 paths). It is the open drift item
    "'Part I' read as '1'", not this change: no patch on 4347 carries a reviewed part opener or a paragraph run.
- Why: the AJK courts' founding provisions are Arts. 42, 42-B, 43 and 44-B (D-139). It is also AJK's constitution,
  and its rights are its most cited text.
- Where: nizam/corpus/segment.py (`paragraph_run_shape_ok`, `_apply_paragraph_run`, the hold-out before the walk,
  the part opener's quote and stop); nizam/workers/segment.py; tools/record_curation_patch.py;
  tools/materialize_multi_instrument.py; tests/test_paragraph_run.py; tools/evidence/ajk-ic-2026-11-25/.

### D-139 · 2026-11-25 · Every court's own site is crawled; the Federal Constitutional Court is landed; Balochistan's files are fetched against robots.txt by owner ruling
Area: L1 precedent acquisition (docs/02 §4, PRECEDENT-MODEL §0, §7) · Status: standing (in progress: crawls running)
- Decision (owner, 25 Nov 2026): the official websites of the courts already held and of the courts not yet held are
  crawled, including the AJK and GB courts; Balochistan's law-report reprints are not used for now (D-120 holds).
  - **The Supreme Court's site opts out of AI** (scp.gov.pk robots.txt: `ai-train=no`, named AI crawlers
    disallowed). The owner ruled it is crawled: the corpus is searched and cited, not trained on.
  - **Balochistan's judgment files sit under `/media/`, which bhc.gov.pk's robots.txt disallows.** Its newer portal
    signs every visitor in with guest credentials built into its script; that route was not used. Owner's choice
    (asked, 25 Nov): fetch `/media/` anyway, slowly (3 s between files). The listing pages are not disallowed.
  - How every crawler behaves: one request at a time with a pause, a generic client name and nothing identifying the
    project or its people; no path a robots.txt disallows, except the owner's Balochistan ruling; no block
    circumvented. ajkhighcourt.gok.pk sends an incomplete certificate chain: the missing RapidSSL intermediate is
    fetched from the certificate's own AIA URL and verification stays on.
- **Federal Constitutional Court (fccp.gov.pk): landed.** The site is a single-page app over a public JSON API
  (`/api/public/site/publications/judgement`, cursor paged; files at `/api/public/site/files/<sha256>`). 140 files,
  each matching the sha256 the API names; 134 released (6 undated), 6 held: 4 long consolidated headers, 2 separate
  opinions (a dissenting and an additional note) issued as files of their own, to be joined to their judgment later.
  - Case types as its headers print them (0136): its own (F.C.P.L.A., F.C.R.P.) and the Supreme Court's for the cases
    transferred to it under the 27th Amendment (C.P.L.A., C.A., C.R.P., C.M.A., Suo Moto, Crl. Org. P., Crl. R.P.).
    A transferred case is keyed under the FCC, the court that decided it (D-125); its earlier Supreme Court record is
    not joined (open).
  - Parser /9: the FCC's 'JUDGMENT OF THE COURT' heading and 'JUSTICE <NAME>:' author line (upper case and a colon,
    so a bench line is never an author).
- **Crawled, by court** (`data/<court>_judgments_scraper.py`, each writing `<court>_judgments.zip` with a manifest the
  worker reads; 25 Nov):

  | Court | Source | Listed | Downloaded | Landed |
  |---|---|---:|---:|---|
  | Lahore HC | data.lhc.gov.pk approved-for-reporting, current and former judges, per year | 9,716 | running | after the crawl; held files skipped by sha256 |
  | Peshawar HC | Reported Judgments, per year | 5,888 | running | after the crawl |
  | Balochistan HC | per-judge reported and significant judgments | 24 judges | running (slow) | after; reprints caught by the gate |
  | AJK Supreme Court | WordPress REST API: posts (some linking Google Drive files the court posted) and uploads | 960 | 959 | after its court is recorded |
  | AJK High Court | the judgment search, both tabs; per-year counts equal the all-years search | 262 | 262 | after its court is recorded |
  | GB Supreme Appellate Court | the static Judgments.html | 752 | 750 (2 links 404 on the court's page) | after its court is recorded |
  | GB Chief Court | the ASP.NET search, every bench and date, each 'View PDF' postback | 154 | 154 | after its court is recorded |

  - The Supreme Court (supremecourt.gov.pk) refused the survey's fetcher (403); not yet crawled.
  - Lahore's listing serial ('2026LHC9081') numbers every Lahore judgment of the year; approved-for-reporting is a
    subset of it. Sindh's portal reports 79,724 uploads by current judges, 87% orders; not yet compared per judge.
- **The AJK and GB courts wait on their founding texts.** A court row cites the provision that creates it (A24).
  - AJK Interim Constitution 1974 (staged, D-096): Art. 42 (Supreme Court), 42-B (binding on all AJK courts), 43
    (High Court), 44-B (binding on subordinate courts). Its 33 unsettled repeated labels are read: the rights Art. 4
    numbers 1–24 (printed indented) were taken for Arts. 5–24 (printed at the margin), and footnotes below the rule
    ('1. Sub Article (1) has been amended two times') for clauses. Settled by `tools/adjudicate_s7_from_source.py`
    readings once landed, then released.
  - GB: the Government of Gilgit-Baltistan Order 2018 appears in force (the Supreme Court's 17 Jan 2019 judgment
    directed a replacement that no source shows was promulgated). s.75 (Supreme Appellate Court), s.78 (binding), s.84
    (Chief Court), s.88 (binding). Official copy: the GB Government portal, without a gazette header; whether it
    carries the 2020 amendment is unconfirmed. To acquire.
- **Law-report notes** (research, 25 Nov; legal-source-scout): a headnote is the publisher's editorial work, likely
  protected (Copyright Ordinance 1962 s.2(p); Eastern Book Co v D.B. Modak, SC India 2008, persuasive), and carries no
  precedential weight (only the decision binds, Arts. 189, 201; 2021 SCMR 1492 as reported). The judgment itself is
  reproducible (s.57(1)(q)(ii)) unless its court prohibits it. Reprint text is not used (D-120); reporter citations
  are kept as identifiers only.
- Golden set: P1-X05 asked what the FCC decided and expected "not held"; it became false, so it is replaced in the
  **test** split (the only test change since D-133, made because its premise failed, not to tune) by P1-I38: the FCC
  holds it may punish contempt under Arts. 204 and 189 (C.P.L.A. 5312/2024 ¶1, ¶6). The FCC text carries a stray
  watermark word ('PAKISTAN') inside sentences: an extraction defect, open.
- Why: coverage is a first-class fact (D-122). The FCC's decisions bind every court, the Supreme Court included.
- Where: data/{fcc,lhc,phc,bhc,sacgb,ajkhc,ajksc,gbcc}_judgments_scraper.py; migration 0136; nizam/corpus/judgment.py
  (/9 `_AUTHOR_TITLED`, `_author`); tests/test_judgment_parse.py; E:/nizam-data/acquire/<court>/ (probes, logs).

### D-138 · 2026-11-25 · The High Courts of Sindh and Balochistan are landed; a judgment agrees with its own case line
Area: L1 precedent (PRECEDENT-MODEL §3, §7) · Status: standing
- Decision: the owner asked for the Sindh and Balochistan archives in E:/nizam-data to be landed.
  - **Sindh: 45,371 judgments released** from 56,227 PDFs and 4,279 official HTML pages (60,506 sources): 6,929
    undated (D-124), 2,272 held, 5,223 scans waiting for OCR, 1,806 duplicates, 2 reprints. The HTML pages are lane
    E1 (docs/02 §4, 0135), read by the same parser through MuPDF's HTML layout.
  - **Balochistan: 30 released.** 1,936 of its 2,001 files are law-report reprints (PLD, YLR, CLC, PCr.LJ, ...), not
    landed (D-120); 32 are scans; 2 held. Its own copies are being crawled (D-139).
  - Case types as each court's headers print them (0132–0134, `tools/observe_case_forms.py`); manifests keyed by file
    name and by sha256; `--held any` re-reads every held file; `--only FILE` re-reads named files after a rule changed.
- **The register letter is part of a Sindh case number**: 'C.P. No. D-1544 of 2026' (division bench) is not 'S-1544'
  (single bench). The case-line grammar keeps it (`D-1544`), with no leading zero after it (`D-01` → `D-1`); 0135 lets
  `judicial_case.case_number` hold it.
- **A judgment agrees with its own case line** (new audit A31):
  - Parser /8 takes the case number and year from the case builder's grammar (`read_case_line`) over the same stored
    words, so they agree by construction. 23,286 judgments read before (23,205 Sindh, 45 SC, 28 LHC, 8 PHC) were
    re-read: `header_differs` 23,286 → 0.
  - Parser /7: a decision date before the case's own year is not taken; the judgment is undated, bounded by its case
    year. 61 judgments carried one (48 Sindh); 56 became undated, 5 carry a case year after today, which is the
    misread part. A31 asserts both rules.
- Parser /7 also reads Sindh's 'ORDER WITH THE SIGNATURE OF THE JUDGE' order sheets, 'Announced on', 'hearing and
  order', 'Dated:' order dates; /6 catches a law report's masthead and its site's URL as a reprint. /10: a reading with
  no body paragraph is held, not released (A25; Sindh C.P. D-649/2020).
- Fallout fixed: the linker prunes the links of judgments a re-read retired (A26: 2,261 statute and 1,165 case rows);
  the privacy builder (/2) redacts every withheld name in the line shown, one-word names included, and `redact` counts
  a three-letter name (A29: a header joining two bail applications showed the second case's victim); alias 201's
  evidence re-pointed to its re-read paragraph (A30, withdrawn and re-inserted); a zip member's time is never later
  than now (it is local time, read as UTC).
- Golden set: P1-X01 (SHC) and P1-X03 (BHC) asked about courts "not held"; replaced in dev by P1-I36 (Sindh, personal
  bona fide need, SRPO 1979: FRA 07/2025 ¶14, CP S-276/2024 ¶14) and P1-I37 (Balochistan, the Special Assistants Act
  2018 struck down: CP 1381/2018 ¶14). The test split is unchanged.
- Open: paragraph numbers printed on a line of their own are sometimes taken as furniture, merging paragraphs (seen in
  SHC CP S-1015/2025; every court shows bare-number furniture, not all of it wrong): a margin-position slice. Sindh's
  2,272 held files (1,351 J3: no case line matching a recorded type; 712 no heading or author line).
- Measured: 55,229 judgments released (SHC 45,371, LHC 3,996, SC 3,105, PHC 2,593, FCC 134, BHC 30); 365,048 new
  passages exported for the GPU (`judgment_chunk --export`, D-132), embedded once the D-139 crawls land. Audit 53
  criteria: A27 waits for that load.
- Where: migrations 0132–0135; nizam/corpus/judgment.py (/6–/10), judgment_case.py; nizam/storage/case_key.py,
  judgment_write.py, privacy.py; nizam/workers/judgments.py, judgment_links.py, judgment_privacy.py;
  tools/observe_case_forms.py; tools/audit/criteria.sql (A31); evals/golden/build_precedent1.py,
  split-precedent-v1.json; tests.

### D-137 · 2026-11-24 · Precedent search reads the case and the court a question names, and windows judgments, not paragraphs
Area: L3 precedent search (docs/04 §6, PRECEDENT-MODEL §4, D-133) · Status: standing
- Decision: the owner asked to fix the judgment-search gaps D-133 and D-136 found before the Sindh and Balochistan
  judgments land.
  - **A case named by its number ranks first** (`precedent.cases_named`). The question is read by the case-line
    grammar after any held court's printed case-type form, anywhere in the question ("Supreme Court Civil Appeal
    No. 415 of 2018"). The grammar (`read_case_line`) moved verbatim from `nizam/corpus/judgment_case.py` to
    `nizam/storage/case_key.py`, so L3 reads L2; corpus re-exports it. Only held case keys are used, and that case's
    judgments rank above any found by likeness, as the citation fast path does for statutes.
  - **The court a question asks for** (`precedent.courts_named`). It is read from the court names and observed
    header forms (`court_alias`), folding "of Pakistan", Sind/Sindh and Baluchistan/Balochistan. A court counts as
    asked for when the question opens with it, when a verb of deciding follows it ("what has the Sindh High Court
    held"), or when its judgments are named ("the Supreme Court's precedent", "judgments of the Peshawar High
    Court"). A court mentioned in passing ("a ceiling after the Federal Shariat Court's decision") is not.
    - One held court asked for narrows the search to it.
    - A court not held returns no hit and a typed `coverage_gap` (court, name, reason): no other court's judgment
      is shown as its view. This is the precedent gate D-133 found missing, for coverage. Search stays discovery
      and passes no answer gate (INV-2 governs answers).
  - **The cited window is of judgments** (`citing_paragraphs`): each judgment by its best citing paragraph (role,
    then mentions) before the window. Counted in paragraphs, a few judgments crowded the rest out (D-136, dev S04).
  - **Urdu, measured and not adopted.** Two variants were tried on dev and neither helped: the statute path's gloss
    (D-105) in the lexical query, with an English dense rendering (MRR on the two Urdu dev cases .167 → .100); and
    the statute lexical query, which drops the question's frame and lost S04. Precedent search keeps the question
    as asked. The measured route for Urdu is the 8B space (D-099: Urdu r@50 1.0 for statutes), not yet built for
    judgments.
- Measured, golden-pk-v1-precedent1 (provisional: the gold is a draft; dev chose, test run once):

  | | Dev, D-136 → D-137 | Test, D-133 → D-137 |
  |---|---|---|
  | hit@10 | .688 → .781 | .650 → .650 |
  | MRR@10 | .391 → .441 | .390 → .371 |
  | recall@50 | .771 → .849 | .900 → .900 |
  | paragraph@10 | .477 → .435 | .692 → .750 |
  | Case lookup | 1/3 → 3/3 | 0/1 → 1/1 |
  | Courts not held, declined | 0/3 → 3/3, plus the 1995 date | 0/2 → 2/2 |
  | Urdu | 1/2 → 1/2 | 0/3 → 0/3 |

  - On test, one provision question (S01, s.22-A(6) CrPC) left the top 10. The test comparison also spans D-134 to
    D-136's relinks.
  - Tests: `tests/test_precedent_query.py` (the asking rule, case keys, the coverage gap); 81 pass.
- Why: a lawyer who types a case number expects that case. A question about a court the corpus does not hold must
  say so rather than answer with other courts' judgments (D-122: coverage is a first-class fact).
- Where: nizam/retrieval/precedent.py (`courts_named`, `cases_named`, `coverage_gap`, `_coverage`);
  nizam/storage/case_key.py; nizam/corpus/judgment_case.py; nizam/storage/judgment_read.py (`citing_paragraphs`);
  evals/precedent_eval.py (`declined`, `coverage_gap`); evals/results/precedent-eval-{dev,test}-d137.json;
  tests/test_precedent_query.py.

### D-136 · 2026-11-24 · A High Court's citation is linked to the law's federal text and its own province's copy, where they are one provision
Area: L2 linking, citation resolver, judgment readers (PRECEDENT-MODEL §4.1, D-097, D-128) · Status: standing
- Decision: item 5, which the owner asked for "fully end to end" ("for 5 we will link with both"). The rules:
  - **The resolver finds the province's copy** (`citations.resolve(..., copies_in=)`). The Lahore and Peshawar
    linkers pass their territory. A law named by a federal alias (PPC, CPC, QSO, MFLO, a reviewed alias) is also
    looked up in Punjab or KP, and that copy joins the alternates after the federal resolution (D-097: federal
    first, typed ambiguity). Retrieval passes nothing, so it is unchanged.
  - **One law in two copies** (`same_law`):
    - the same words once case, punctuation, "the" and "No." are folded;
    - a year or a kind word counts only when both titles print one;
    - two printed years that differ are two laws.

    "Pakistan Penal Code" and "Pakistan Penal Code, 1860" are one law. "Code of Criminal Procedure, 1898" and the
    pre-1947 archive "The Code of Criminal Procedure Act, 1898" are not.
  - **A copy is linked only where its unit is the same provision** (linker `nizam.judgment_links/7`):
    - the same label at the same depth;
    - content words of heading and opening text overlapping by at least half, with boilerplate ("whoever … shall be
      punished with imprisonment") set aside;
    - only federal law and the court's own territory (no AJK copy under a Lahore judgment); the Supreme Court
      federal only.
  - **Readers read every copy.** `citing_paragraphs` (the precedent "cited" generator) and `provision_judgments`
    ("cases on this section") match `dst_provision_id` or any alternate, using a GIN index on `alternates` (0131).
    A26 now also requires every alternate to be released law.
- What reading the copies found:
  - **The Punjab copy is not always the same text.** Punjab's PPC is an older reprint. Its s.489-F is a prize-bond
    offence, and its ss.375/376 read "repealed by the Offence of Zina (Enforcement of Hudood) Ordinance, 1979,
    s.19". These are refused (tests).
  - **Where a provincial primary differs from the federal unit** (570 citations: the Family Courts Act 1964, the
    Police Order 2002, the CNSA, the Limitation Act), the provincial text is the province's amended law. D-128's
    territory-first primary stands there, and the federal unit is correctly not tied to it.
  - **The archive CrPC.** 731 "302/324 Cr.P.C." citations had resolved, under /6, into the pre-1947 archive text
    (`historical`) because the current Code has no unit so labelled. Most are PPC sections attributed to the wrong
    code. They are now `unit_not_found`, which is not a guess.
- Measured, all 9,694 judgments relinked under /7:
  - Resolved 109,007 of 146,182; under /6, 109,887 (the 880 difference is the archive-CrPC links above).
  - 40,167 citations are also linked to another copy, 7,594 of them Lahore citations filed under the Punjab copy.
  - A dry run on 160 High Court judgments, read: copies linked include Punjab PPC ss.34, 11 and 295-A. Copies
    refused include PPC ss.375/376 (Punjab stub), Police Order s.18 (different provisions), unserved as-made
    copies with no text, and units at different depths.
  - **Privacy rebuilt from the new links** (`nizam.judgment_privacy/1`): no judgment lost a redaction. Two gained
    one (family law now resolved), for 572 judgments and 1,282 names.
  - Precedent dev, against /5 (test not rerun): hit@10 .719 → .688, MRR@10 .382 → .391, recall@50 .786 → .771,
    paragraph@10 .413 → .477.
    - The one hit lost is S04 ("judgments on s.489-F PPC"). Its gold judgment is still linked, but the cited
      generator's window counts paragraphs, so judgments with many citing paragraphs now crowd it out of the top
      200 (open).
    - S03 rose from rank 10 to 1.
  - `./nz audit` 52/52; 168 tests pass; golden citations 580/581, 0 wrong.
- Why: a Lahore lawyer reading the Punjab Code's s.34 should find the Lahore judgments on s.34. A province's
  different provision under the same number must never collect them.
- Where: infra/postgres/migrations/0131_jsr_alternates_index.sql; nizam/storage/citations.py (`same_law`,
  `copies_in`), judgment_linking.py (`same_provision`), judgment_read.py; nizam/workers/judgment_links.py;
  tools/audit/criteria.sql (A26); tests/test_citation_guesses.py, test_judgment_db.py;
  evals/results/precedent-eval-dev-d136.json.

### D-135 · 2026-11-24 · D-134's open items closed: the rare names read, "of the Act." refers back by kind, compilation copies kept
Area: L2 citation resolver and linking, corpus identity (D-134, D-127, PRECEDENT-MODEL §4.1) · Status: standing
- Decision: the owner asked to "close these open fully". D-134 left three items open.
  1. **The 1,584 rarer printed names** were put on a second sheet (`docs/alias-review/law-aliases-2026-11-24-tail.csv`).
     `alias_review.py build --name tail` skips every name already decided on an earlier sheet. There were 1,597
     rows, decided as follows:
     - **472** one judgment and no year: decided by D-134's rule (a judgment's own short name).
     - **417** with no candidate law at all, by initials or title: not held.
     - **584** whose candidates matched neither on initials and year nor on every word, year and province: those
       candidates are other laws.
     - **128** strong proposals, every one read: **107 aliases**, 21 refused. The refused include a kind that
       differs (an "Act, 1963" against a held Ordinance), a misprint naming two Orders, and three names that are the
       held title itself.
     - **New loader rule:** an alias never sits on a key that is the held title folded ("Specific Relief Act 1877"
       with a stray apostrophe). Such an alias would override the title search, and its territory preference, for
       every correct citation of the law.
     - **Active aliases: 188.**
  2. **"of the Act." refers back** (`judgment_linking.back_reference`, linker /6). A stopped kind word, optionally
     with "the said/same/aforesaid" and a year ("Article 79 of the Order, 1984"), inherits the judgment's last-named
     law when the kind and the printed year agree. "The amending/principal/repealed Act" never inherits. A
     kind-only name is no longer remembered as the judgment's last law, which used to block later bare citations.
     D-127's refusal to look such a name up by title is unchanged. Only the judgment's own named law is taken.
  3. **The 34-law compilation (document 4497) and its kind.** All six multi-law documents were compared with their
     single-law twins: 17 pairs, word-level similarity of the current released text.
     - Only one pair is the same text: the Sindh Local Government (Local Fund Budget) Rules 2001, 3389 against 2985,
       10 units, similarity 1.000.
     - The other 16 differ (0.44–0.98). They are different consolidations: the NAO 2008 against 2026, the Civil
       Servants Act 2016 against 2025, and the reverse for the Service Tribunals Act (2014 in the compilation, 1981
       standalone).
     - So `duplicate_of` (0062) does not apply: it would withdraw a different text of a law. Every route the corpus
       has skips a released copy by design, and none is built here for one 10-unit rule.
     - No fixed preference between the copies is safe either, since each order picks an older text somewhere.
     - The resolver keeps the copies of one law as one law, the others as alternates (D-136 checks them).
     - The underlying defect is two different texts of one law, both served as current. It is registered below as
       a version-modelling item.
- Measured, all 9,694 judgments relinked under /6 (statute citations):

  | | /5 (D-134) | /6 |
  |---|---:|---:|
  | Resolved | 99,708 | 109,887 |
  | Law not held | 7,044 | 8,361 |
  | No law named | 32,618 | 19,561 |
  | Unit not found | 6,812 | 8,373 |

  - Read: 30 stopped references that now inherit, all correct (kind and year agree), and 20 links through tail
    aliases, all correct.
  - "Law not held" rose by inheritance of named laws the corpus does not hold. "Unit not found" rose where a law
    is now named but the section is not in it.
- Why: every printed name of a law that a person can read as one law should link, and none that cannot. A back
  reference inherited by kind is the judgment's own words, not a guess.
- Where: tools/alias_review.py (`--name`, decided-key skip, title-key rule); docs/alias-review/*-tail.*;
  nizam/storage/judgment_linking.py (`back_reference`, `may_inherit` year); nizam/workers/judgment_links.py;
  tests/test_citation_guesses.py. D-127 is partly superseded on inheritance only.

### D-134 · 2026-11-24 · Law aliases from a review sheet; a title stops at its sentence; a law is inherited only by its own kind
Area: L2 citation resolver (shared by L3 and the judgment linker), schema, linking (PRECEDENT-MODEL §4.1, D-127) ·
Status: standing
- Decision: the owner asked for item 4, the alias review sheet, "fully end to end". D-127 had left two kinds of miss
  "for an alias slice": practitioner abbreviations (NAB Ordinance, ITO 2001, STA 1973) and spellings the title
  search does not join (Qanoon-e-Shahadat, Sindh/Sind).
  - **The grammar first** (`nizam/storage/citations.py`). Of the 17,420 citations recorded `law_not_held`, most were
    not names at all:
    - **A title stops at its sentence's end**, a word or year and its full stop before the next capital. The stop is
      kept, so "of the Act." stays a kind of law (D-127). It also stops before the next citation's unit word ("the
      General Clauses Act and Article 4"). The scan then resumes at the cut, so the next citation is read.
    - **Trailing parentheses are dropped** ("(V of 1908)", "(Act XLV of 1860)", "(Cr.P.C.)", '("FIO")'). A year
      printed only inside them is kept: "Contempt of Court Ordinance (Ordinance V of 2003)" is the 2003 Ordinance.
    - A sub-clause swallowed ahead of the name is dropped: "Article 8(1) and (2) of the Constitution".
    - Re-read under these rules: 11,099 name only a kind of law, 687 find their law by its title, 319 match a code
      alias, and 5,315 remain.
  - **The review sheet** (`tools/alias_review.py build`, `docs/alias-review/law-aliases-2026-11-24.csv`, .md). Each
    printed name still unmatched in 3 or more judgments or 10 or more citations is a row: 172 rows, carrying counts,
    printed forms, three passages and up to three candidate laws (by initials or trigram). Each row was decided by
    reading its passages and the candidate's title in the corpus:
    - 81 alias, 34 ambiguous, 30 not held, 13 foreign, 11 not a law, 3 historical.
    - **Rules:**
      - an alias needs two judgments, or a year that makes the name unique (a short name one judgment defines is
        its own);
      - a year that disagrees is not corrected ("Specific Relief Act, 1977");
      - act numbers ("Act V of 1962"), First Schedule Articles of the Limitation Act, and names without their
        province ("Cooperative Societies Act, 1925") stay unresolved.
  - **`law_alias` (0130)**:
    - **What a row holds:** key (`law_key`), printed forms, the law by source document with the title and
      jurisdiction the resolver searches, basis, evidence passages, sheet, reviewer and date.
    - **Rules:** one active row per key; rows are withdrawn, never deleted.
    - **Who reads it:** `resolve()` reads it after the code aliases, for retrieval and the linker alike.
    - **Loading:** `load` refuses a row unless the document holds one law, its title finds that law (or a
      same-titled copy) first, a printed year is the title's, and every evidence passage is a released paragraph
      printing the form.
  - **Inheritance (0121) is checked by kind.** Reading 40 alias links found two wrong, both inherited:
    - "Section 25 of the Hisba Bill" took the NAB Ordinance;
    - "section 3 of the Ordinance" took the PC Act.

    Now a citation whose printed title names something that is not a law never inherits, and one naming only a
    kind ("of the Ordinance", "of the Code") inherits only a last-named law of that kind
    (`judgment_linking.may_inherit`). A sample of 30 links this stopped were all corrections: "Article 13(2) of the
    Order" no longer takes the Constitution, and "section 65 of the Act" no longer takes the CrPC.
  - **Linker `nizam.judgment_links/5`; audit A30** (aliases name one held law, evidence printed, none left
    unapplied).
- Measured, 24 Nov 2026, all 9,694 judgments relinked (statute citations):

  | | /3 (D-128) | /4: grammar and aliases | /5: + inheritance by kind |
  |---|---:|---:|---:|
  | Resolved | 99,384 | 103,758 | 99,708 |
  | Law not held | 17,420 | 7,755 | 7,044 |
  | No law named | 21,164 | 27,018 | 32,618 |
  | Unit not found | 7,916 | 7,651 | 6,812 |
  | Total | 145,884 | 146,182 | 146,182 |

  - Resolved through a reviewed alias: 2,694.
  - **The resolved count under /5 is close to /3, but the links differ.** About 4,000 links gained from the grammar
    and aliases replace about 4,000 inherited links of the wrong kind, now removed.
  - Samples read: 40 alias links, all 38 with the law named correct (the 2 wrong were inherited, fixed above); 30
    inherited links under /5, all correct.
  - The golden citation check is unchanged: 580 of 581, 0 wrong.
  - Precedent search on dev is unchanged within noise: hit@10 .719 → .719, MRR@10 .376 → .382, paragraph@10 .435 →
    .413. Test was not rerun.
  - `./nz audit` passes 52/52.
- Open (also in the open questions):
  - "of the Act." with a full stop still never inherits (D-127), even where the kind matches ("section 55 of the
    Act." after the Land Acquisition Act).
  - Document 4497 is a 34-law compilation repeating the NAO, the Civil Servants Act and the Service Tribunals Act.
    It is not marked `duplicate_of`, and the title search prefers its copies.
  - 1,584 rarer printed names (2,222 citations) are not on the sheet.
- Why: a law named in a judgment and not linked hides that judgment from "cases on this section". A wrong link is
  worse than none (D-127), so every alias rests on reading, and inheritance now checks the kind of law named.
- Where: infra/postgres/migrations/0130_law_alias.sql; nizam/storage/citations.py, unit_search.py
  (`Session.law_alias`), judgment_linking.py (`may_inherit`); nizam/workers/judgment_links.py; tools/alias_review.py;
  docs/alias-review/; tools/audit/criteria.sql (A30); tests/test_citation_guesses.py, test_judgment_db.py,
  test_historical_expression.py; evals/results/precedent-eval-dev-d134.json.

### D-133 · 2026-11-24 · A precedent stratum of the golden set: 58 questions, gold at judgment paragraphs
Area: evaluation (docs/10 §4–§5, INV-4; docs/PRECEDENT-MODEL.md §8 build order step 5) · Status: standing
- Decision: the owner asked for item 3, a test set for judgment search, after item 2.
  `evals/golden/build_precedent1.py` builds `golden-pk-v1-precedent1`: 58 cases over the Supreme Court and the
  Lahore and Peshawar High Courts.
  - **Gold** is judgment paragraphs. Each is named by its source document id and one paragraph (printed number or
    `#ordinal`), or the whole judgment for a case lookup. Court, case, date and text come from records. docs/10
    already says labels end at judgment paragraphs; this is that rule applied.
  - **Strata (the docs did not fix them for precedent; this sets them):**
    - issue 35 (SC 15, LHC 10, PHC 10);
    - authority 1, temporal 3, case_lookup 4, provision 4;
    - Urdu and Roman Urdu 5, each in its English case's family;
    - unanswerable 6: five courts not held, and one date (1 Jan 1995) before any held judgment existed.
  - **Found by reading, not by the system:** gold paragraphs were picked by plain SQL text match
    (`peek_judgment.py`) and read. The gold names some of the judgments that answer, not all, so no precision is
    reported.
  - **Checks in the builder (`precedent_common.py`):**
    - each gold judgment existed at `as_of`, and each trap did not;
    - each answer case's regexes match its gold paragraphs;
    - abstain codes are checked against the release;
    - the author's binding-status reading (Art. 189 binds every court to the SC; Art. 201 binds a High Court's own
      subordinate courts) is compared with the recorded rules, and any difference is reported.
  - **Split by family, not by case.** docs/10 §4 requires it, and the statute split (D-098) does not do it.
    Families are ordered by sha256 within answerable and unanswerable, and the first 60% are dev: 36 dev cases, 22
    test. Recorded in `split-precedent-v1.json`.
  - **Harness:** `evals/precedent_eval.py` reports the following over `precedent.search` with the case's forum:
    - hit@10, MRR@10, recall@10 and recall@50 over gold judgments;
    - paragraph@10;
    - leaks;
    - authority agreement;
    - what an unanswerable query returns.
- Measured, 24 Nov 2026 (provisional: the gold is a draft; no tuning was done; test run once), hybrid:

  | Split | Answerable | hit@10 | MRR@10 | recall@50 | paragraph@10 | Leaks | Authority (agree / disagree / not recorded) | p50 |
  |---|---:|---:|---:|---:|---:|---:|---|---:|
  | Dev | 32 | .719 | .376 | .786 | .435 | 0 | 33 / 0 / 1 | 0.75 s |
  | Test | 20 | .650 | .390 | .900 | .692 | 0 | 19 / 0 / 1 | 0.80 s |

  - **Issue questions:** hit@10 .81 dev and .79 test.
  - **A case asked by its number:** found in 1 of 4. Precedent search has no case-number fast path, though the
    grammar exists (`judgment_case.read_case_line`).
  - **Provision questions** rank low (dev MRR .07).
  - **Urdu and Roman Urdu:** found in 1 of 5. The same questions in English are found.
  - **Courts not held:** each returns 50 judgments of other courts. Search is discovery and passes no gate, so a
    precedent gate (docs/04 §6, not built) must decline to present them as the asked court's view.
  - **The 1995 question** returns nothing, which is correct.
  - **Authority before 13 Nov 2025:** the recorded rules give the SC's authority as `not_recorded` (three cases at
    2023 and 2025 dates). Rules exist only where a dated text of Arts. 189 and 201 is held: 2016, and from 13 Nov
    2025 (SC) and 19 Jun 2026 (High Courts). This is D-116 refusing rather than guessing. Closing it needs dated
    Constitution texts for 2017–2025.
- Why: no precedent claim can be tuned or defended without the instrument (docs/10). The precedent gate and any
  ranking change need dev figures first.
- Where: evals/golden/{build_precedent1.py, precedent_common.py, peek_judgment.py, split-precedent-v1.json,
  golden-pk-v1-precedent1.draft.jsonl/.md, README.md}; evals/precedent_eval.py;
  evals/results/precedent-eval-{dev,test}.json; tests/test_precedent_golden.py.

### D-132 · 2026-11-24 · Judgment chunks are embedded on a Kaggle GPU in generation 1, as the statutes were
Area: L2 retrieval storage, judgment chunks (docs/PRECEDENT-MODEL.md §6.1, D-098, D-121) · Status: standing
- Decision: the owner asked "can't we do on kaggle gpu?" when the CPU run over the Lahore and Peshawar paragraphs
  was slow. The run moved to the GPU, under generation 1's rule:
  - The model is BAAI/bge-m3 at the pinned commit, with its own CLS pooling, 512 tokens, fp16 and normalised. The
    stored vector is the sign of the first 1,024 dimensions. The statute chunks were embedded the same way on a
    Kaggle T4 (D-098, `tools/kaggle/embed_kernel.py`). Queries stay int8 ONNX on the CPU.
  - `nizam.workers.judgment_chunk --export DIR` writes every chunk a released body or footnote paragraph should have
    and does not. The passage is written exactly as the CPU encoder reads it (`passage_text`), and the row it becomes
    is written beside it. A paragraph a stopped run left half-chunked is completed, not skipped.
  - `tools/kaggle/judgment_embed_kernel.py` (pushed by `kg.sh jembedpush`) embeds them. `--load EXPORT RUN --apply`
    COPYs the bits into `judgment_chunk` under the one active CPU generation and the same chunker.
- Measured, 24 Nov 2026:
  - 111,182 chunks were embedded on a T4 in about 25 minutes. The other 113,341 of the 224,523 were embedded earlier
    on the laptop.
  - Same space, checked: on 40 random passages, the GPU fp16 bits and the laptop's int8 encoder differ in a median
    61 of 1,024 bits for the same passage, against 366 for different passages.
  - A27 passes, and `./nz audit` passes 51/51.
  - Changes to tests: `test_a_named_section_reaches_the_judgments_that_cite_it` assumed every hit was a Supreme Court
    judgment. It now asserts the recorded rule per court: a Punjab subordinate court is bound by the SC and the
    Lahore High Court, and a Peshawar judgment reaches it as `not_binding`.
- Why: generation 1 is defined by the model, revision, pooling and sign rule, not by the device. The statutes already
  live in this space through a GPU run, so judgments embedded the same way are searched by the same query vector.
- Where: nizam/workers/judgment_chunk.py (`_missing`, `export`, `load`); tools/kaggle/judgment_embed_kernel.py;
  tools/kaggle/kg.sh (`jembedpush`); tests/test_judgment_db.py.

### D-131 · 2026-11-24 · Names are withheld in sexual-offence, minor, family and medical judgments, on a recorded basis
Area: owner ruling, schema, L2 readers, L3 precedent search, privacy (docs/PRECEDENT-MODEL.md §6.3, D-122) · Status: standing
- Decision: the owner asked for item 2, the party-name rules, "end to end". D-122 had set the rule: parties_raw is
  internal, the parties shown are redacted for sensitive categories, each category names its basis from the corpus
  or is marked product policy, and party names are not a search key.
  - **The bases, read in the served laws on 24 Nov 2026** (0128, `sensitive_category_source`). They are cited as the
    court records are (observation, ordinal, unit label, exact words). The migration refuses a quote that is not
    printed, and A29 asserts it on every run.

    | Category | Kind | What the corpus says |
    |---|---|---|
    | Sexual offence | statute | PPC s.376A(1) forbids publishing what identifies the victim of an offence under ss.354A, 376, 376A, 377, 377B; its Explanation exempts judgments **in law journals** only. The Anti-Rape (Investigation and Trial) Act 2021 s.26(1): "No person shall disclose or reveal the identity of any victim" |
    | Minor | follows statute | Juvenile Justice System Act 2018 s.13(1) forbids publishing a juvenile's identity; its Explanation says publishing a High Court or Supreme Court judgment is not an offence. Withheld anyway, following the section's purpose |
    | Family | product policy | no provision found (searched) |
    | Medical | product policy | none found for judgments (the Sindh HIV and AIDS Act covers a child tested for HIV, which is narrower) |

  - **What marks a judgment** (`sensitive_category_rule`, data, not code):
    - a resolved citation of a category's law (PPC ss.354A/376/376A/377/377B, the Anti-Rape Act, the Zina Ordinance
      s.10, the Juvenile Justice Acts, the Guardians and Wards Act, the Family Courts Acts, MFLO, the Dissolution of
      Muslim Marriages Act, the Dowry Acts, the mental health and HIV Acts);
    - words in the header ("Judge Family Court", "minor", "through his father", "of unsound mind");
    - for a sexual offence only, the offence named in the body ("zina-bil-jabr", "rape", "prosecutrix"; 0129).
      Measured: 240 judgments speak of the offence and only 122 cite the section in a resolving form. "Minor" is
      too common a word ("minor discrepancies") for the body rule.

    Marking leans towards over-marking, because a wrong mark only hides a name.
  - **What is withheld** (`nizam.judgment_privacy/1`, `judgment_sensitivity` and `judgment_display`, derived and
    rebuilt from the release):
    - the parties line shown, the first "A v. B" in the header, keeps a side only when it names no person (the
      State, a government, an office, a company); any side that names a person is withheld whole;
    - names withheld (internal, never returned): the persons on the parties line; for a sexual offence, the persons
      the body names as victim, prosecutrix or abductee, and every "Mst."/"Miss" name; in every marked judgment,
      the persons named as a minor or juvenile ("minor Zaryab Khan", "his minor son namely Arsalan").
  - **What readers do** (`nizam.storage.privacy`, `judgment_read`, `precedent`):
    - every paragraph and search hit returned replaces each withheld name with "[name withheld]". A one-word name
      that is a common word ("Ali") is replaced only in a sexual-offence judgment, where the victim's identity is
      statutory;
    - the judgment page and hits carry `parties_display` and `privacy`: whether names are withheld, and each
      category with its kind and recorded basis;
    - a precedent search naming a withheld person (the whole name, or two of its words) never returns that judgment;
      the trace counts such refusals.
  - judgment.parties_display (0119) stays unused: the judgment row is append-only evidence.
  - Run order after a judgment release: cases, then the linker, then this builder.
- Result (9,694 released judgments; audit A29):

  | | Judgments |
  |---|---:|
  | Names withheld | 570 |
  | of which sexual offence | 264 |
  | of which family | 270 |
  | of which minor | 97 |
  | of which medical | 3 |
  | Names withheld, in all | 1,278 |
  | Parties line not read (none printed in a form found) | 2,466 |

  Measured after redaction over all 264 sexual-offence judgments: no "Mst."/"Miss" name and no "victim namely …"
  name remains (3,231 replacements). Reading samples found and fixed five defects before release:
  - a side carrying header words beside a person was judged an institution and shown. Now any person withholds
    the side;
  - "Judge" cut an office short;
  - case lines and column labels stuck to names;
  - child victims were missed;
  - a sentence opener was taken as a name.

  Two patterns also backtracked without end on Peshawar's OCR text (a dash run, a space run) and were rewritten,
  with tests.
- Limits, stated: a name the text never ties to a party line, "victim", "minor" or an honorific is not found.
  Judgments with no parties line read get only their body names withheld. A party's name stays searchable in a
  judgment of no category (D-122's general "not a search key" is enforced only where names are withheld; open
  question below).
- Why: s.376A(1) and the Anti-Rape Act make a victim's identity a legal matter for this product, which is not a law
  journal. The other categories follow the law's purpose or D-122's policy, and say which.
- Where: infra/postgres/migrations/0128_judgment_privacy.sql, 0129_privacy_body_words.sql; nizam/storage/privacy.py;
  nizam/workers/judgment_privacy.py; nizam/storage/judgment_read.py; nizam/retrieval/precedent.py;
  tools/audit/criteria.sql (A29); tests/test_privacy.py, tests/test_judgment_db.py.

### D-130 · 2026-11-23 · Peshawar High Court lands; a text layer must be readable (J9); a register lists all that is not added
Area: owner ruling, L1 parser, schema, linking, process (docs/PRECEDENT-MODEL.md §7 step 6) · Status: standing
- Decision: the owner asked for the Peshawar High Court "end to end fully", and for everything not added (laws and
  judgments, scans and the rest) to be written down for later.
  - **Only the court's own folder is read.** `judgments_peshawar_high_court.zip` also carries the whole SC archive,
    the SECP and FBR law files and GB codes. `nizam.workers.judgments --member-prefix
    judgments_peshawar_high_court/` reads only that folder, and only a manifest inside it. Another set is never
    recorded as this court's, and another set's URL is never attached to this court's file.
  - **0126, case types, as observed.** 25 types read from the case lines of the court's headers, with every
    printed spelling seen (the bail application alone prints as "Cr.Misc.BA", "Cr.M(BA)", "Cr.MBA", "BA", "Bail
    Petition" and more). A name the court never prints is not invented: "F.A.B." (banking appeals) keeps its
    printed name, and "COC" is contempt. **0127:** the court's name as its own templates type it ("PESHAWAR HIGH
    OURT", "PESHAWARHIGH COURT", letter-spaced). OCR garble is not made an alias.
  - **The parser, `nizam.judgment/5`:**
    - **Gate J9, a readable text layer.** Many Peshawar files are scans carrying the court's own rough OCR ("IN
      TIIE PESIIAWAR IIIGII COUITT"). Such text is not released as citable. A file whose words (three letters or
      more, at least 200 counted) are less than 90% known goes to the OCR lane with its score. "Known" means found
      in a word list built from the typed text of released SC judgments (`tools/build_judgment_vocab.py`, words in
      at least 3 judgments, 22,956 words; versioned with the parser). The check runs before the court or heading is
      looked for. Measured on full text before the threshold was set: every clean Lahore file scores 0.94 or more,
      and about one Peshawar file in ten falls below, some to 0.35. Of the judgments already released (SC and
      LHC), one falls below; it stays released and is listed for an OCR re-read.
    - Peshawar's decision date: "Announced. 14.11.2017", "Announced: 13.10.2020", "ANNOUNCED. Dated: 22/07/2015",
      "Announced. Dt: 18.5.2016". Undated Peshawar judgments fell from 79% to 27% with this alone. The same form
      dates about 1% more of a Lahore sample, so Lahore is not re-read.
    - Peshawar's order-sheet column header, "Order or other Proceedings with Signature of Judge(s)".
    - A reprint whose series letters are spaced ("P L D 2011 Peshawar 120") is caught (D-120).
  - **Links:** a Peshawar judgment's bare title resolves to KP law first, then federal law, in KP's served
    text (D-128's territory rule).
  - **The register** (`tools/pending_register.py` → `docs/PENDING-REGISTER.md`, `docs/pending/laws.csv`,
    `docs/pending/judgments.csv`) is generated from the database and the staging lists, never edited by hand,
    and rerun after any landing. A staging row whose file has since landed is dropped by its sha256.
- Result, Peshawar High Court (5,713 files in the court's folder, 5,704 distinct):

  | Outcome | Files |
  |---|---:|
  | Released | 2,593 |
  | of which dated ("Announced", "decided on", date of order) | 1,900 |
  | of which undated (D-124) | 693 |
  | To OCR: no text layer | 1,598 |
  | To OCR: text layer not readable (J9) | 193 |
  | To OCR: too thin, or Urdu | 27 |
  | Law-report reprints, not landed (D-120) | 653 |
  | Held: court not printed or garbled (298), no heading (200), no case line (141) | 639 |
  | Duplicate | 1 |

  A sample of 30 dated readings was read against their printed phrase: every date was the one printed. No dated
  Peshawar judgment has a hearing after its decision.
- Why: the owner asked for Peshawar end to end. A garbled text layer released as citable text would put misread
  section numbers and names into links and answers. Sending it to OCR is the honest route (INV-1). The register
  turns "what is left" into a list that can be worked down.
- Where: infra/postgres/migrations/0126_phc_case_types.sql, 0127_phc_court_aliases.sql; nizam/corpus/judgment.py,
  nizam/corpus/data/judgment_vocab.txt; nizam/workers/judgments.py; tools/build_judgment_vocab.py,
  tools/pending_register.py; docs/PENDING-REGISTER.md, docs/pending/; tests/test_judgment_parse.py.

### D-129 · 2026-11-23 · L3's measured figures stand under D-126; custom plans cost no measurable latency
Area: L3 evaluation (docs/RETRIEVAL-STATE-2026-11-21.md) · Status: standing
- Decision: the open question D-126 raised, whether L3's figures were taken under generic plans, is closed. No
  figure changes.
  - **Measured on dev** (golden split v1, 276 answerable cases; `evals/lexical_benchmark.py` through a wrapper that
    restores the old connection options). BM25, fused lexical and hybrid were run under both plan modes. All 276 result
    lists are identical in every arm, so recall, MRR and NDCG agree to every digit:

    | Arm | recall@10 | recall@50 | NDCG@10 |
    |---|---:|---:|---:|
    | BM25 | .248 | .393 | .165 |
    | Fused lexical (D-097) | .438 | .607 | .296 |
    | Hybrid (D-098) | .620 | .768 | .450 |

    Hybrid recall@50 is .768 against .765 on 21 Nov. The difference comes from laws added since (D-113, D-115), not
    from plans. Test was not run (it is scored once per decision, and nothing here is a decision about retrieval).
  - **Latency,** hybrid on an idle machine, three runs: custom 1,083 ms p50 (1,429 p95), generic allowed 1,050 ms
    (1,298), custom again 914 ms (1,200). Two runs of the same setting differ by more than the two settings do, so
    custom plans have no measurable cost. A first run that appeared ~500 ms slower overlapped a Lahore dry run on the
    same machine, and is discarded.
- Why: the retrieval path's pg_search body windows evidently did not hit the generic-plan fault that the
  title lookup did. The fix (D-126) stays, because the title lookup is on the same connections.
- Where: evals/results/dev-plans-{auto,custom}-2026-11-23.json, dev-latency-{custom,auto,custom2}-2026-11-23.json.

### D-128 · 2026-11-23 · The Lahore High Court lands: its case types, its two layouts, its territory for links
Area: owner ruling, L1 parser, schema, linking (docs/PRECEDENT-MODEL.md §7 step 6) · Status: standing
- Decision: the owner asked to start with the Lahore High Court. Its archive is ingested by the Supreme Court
  pipeline, with these additions.
  - **0124, case types and names, as observed.** 31 case types with their printed forms, read from the case lines
    of 4,299 headers in `lahore_HC_judgements.zip`. A full name the headers do not print is taken from the
    archive's own category label: PTR is "P. for Tax Reference"; C.O. is "Civil Original (Commercial)"; Crl. Org.
    is "Criminal Original", contempt. Two printed forms of the court's name are observed aliases: letter-spaced
    (15 headers) and "LAHORE HIGH C OURT" (2).
  - **0125:** a case number's registry suffix may be up to three letters ('2143-CB', cancellation of bail;
    '4-RWP'). Before, two different cases could share one key.
  - **The parser, `nizam.judgment/4`.** Readings already released stay as they were read.
    - "ORDER SHEET" and "JUDGMENT SHEET" are form titles, not opinion headings.
    - **Order sheet** (form HCJD/C-121): the order begins at the first line opening with a date, within 25
      lines of the column header "Order with signatures of Judge … where necessary". Lines before it (case line,
      parties, column labels) are header. Its decision date is that **date of order**. A sheet that opens another
      proceeding with a different date (a date line followed by an appearance line) holds several orders, and is
      released undated with that reason.
    - **Judgment sheet:** the hearing date, the counsel list and sometimes the case line are printed between the
      JUDGMENT heading and the author line. They are header.
    - The author line may omit its comma ("Raheel Kamran J:-", "AHMAD NADEEM ARSHAD-J,").
    - Decision dates also read: "Signed on 25.02.2025" (signed_at); "pronounced on 13.03.2023" (announced);
      "decided on 12th March, 2015" in the header (date_of_decision).
    - A case line opening "Case No." or an enumerator ("1. Crl. Appeal No.646 of 2013") is read. The bench printed
      in the header is the seat (Multan, Bahawalpur, Rawalpindi).
    - **A lone "Judge" line** closes an opinion only near the end of the text, or when what follows reads as a
      closing or a new opinion. Narrow order-sheet columns wrap "the learned Civil / Judge / Sahiwal", and the rest
      of the order had gone into the closing, out of the searchable body.
    - A law-report reprint that opens with its series ("PLJ 2020 Lahore 555 (DB)") is caught (D-120).
  - **Cases decided together, from the header** (`nizam.judgment_cases/2`, both courts). A High Court prints each
    case it decides on its own line ("Murder Reference No.290 of 2015 … Criminal Appeal No.1112-J of 2015"), and
    752 of 3,996 Lahore headers list more than one. Every case line of the court's own types in the header becomes
    a `joined` case of the judgment, with its own type and year. A case line is not read when it is the case below
    or the case an application is made in. That means it is preceded by "in", "against", "from", "passed", "vide"
    or "impugned", or it sits in a parenthesis opened by such words ("(Against the judgment … passed by the Lahore
    High Court in Criminal Appeal No.300-J/2013 and Murder Reference No.138/2011)"), or its form is part of another
    name ("Murder Reference"). Read: a sample of 25 Lahore and 30 Supreme Court header joins, after the
    parenthesis rule, all cases decided in that judgment. The first SC sample had shown the two lower-court
    patterns now refused.
  - **Links in the court's territory** (`nizam.judgment_links/3`, PRECEDENT-MODEL §4.1). A bare title in a
    Lahore judgment resolves to Punjab's law first, then federal law, and the version linked is the one served in
    Punjab on the decision date (`nzq.territory`). Supreme Court judgments are unchanged: federal first, no
    territory. `unit_search.Session` takes the preference order, and its default stays federal, so retrieval is
    unchanged.
- Result, Lahore High Court archive (4,557 files, 4,550 distinct):

  | Outcome | Files |
  |---|---:|
  | Released | 3,996 |
  | of which dated | 1,478 |
  | of which undated (D-124): a hearing date and nothing else printed | 2,518 |
  | Held: no heading and no court printed (2013 order sheets), or not this court (the Service Tribunal) | 199 |
  | Held: J3, no case line read | 40 |
  | Law-report reprints, not landed (D-120) | 197 |
  | Waiting for OCR (D-114) | 117 |
  | Duplicate | 1 |

  - Most Lahore judgment sheets leave "Announced in open Court on ______" blank and print only the date of
    hearing. They are released undated, never dated from the hearing or the folder year.
  - The archive's file timestamps are all September 2026 (the download), so an undated Lahore judgment is bounded
    by its hearing date below and September 2026 above. That is wide, but true. A portal recrawl with the court's
    own decision dates would narrow it.
  - A sample of 30 dated readings was read against their printed phrase, and every date was the one printed.
- Why: the Lahore High Court is Punjab's highest court and the court most of the corpus's users answer to (Art.
  201, recorded). Every rule above is read from the court's own pages, and nothing is dated by a guess (INV-1).
- Where: infra/postgres/migrations/0124_lhc_case_types.sql, 0125_case_number_suffix.sql; nizam/corpus/judgment.py;
  nizam/corpus/judgment_case.py; nizam/storage/unit_search.py; nizam/workers/judgment_links.py;
  tests/test_judgment_{parse,case}.py.

### D-127 · 2026-11-23 · A citation that names only a kind of law, or a law of another year, is not resolved by a guess
Area: L2 citation resolver (shared by L3 and the judgment linker), linking · Status: standing; partly superseded by
D-135 (a kind-only name may inherit the judgment's own last-named law of that kind)
- Decision: `nizam.storage.citations.resolve` refuses two guesses. Both used to resolve, because the title search
  returned whatever matched and the most relied-on law won.
  - **A kind word is not a name.** "Section 4 of the Act.", "the Act, 2013", "the Amending Act" and "the said
    Ordinance of 1979" name no law. They are left unresolved, "no law named … not guessed", and the linker records
    `no_law_named`. Before this, 722 citations of "the Act." went to the Trusts Act 1882, "section 14 of the Act,
    1940" to the Arbitration Act 1940, and "section 24 of the Act, 2013" to the Trade Organizations Act 2013.
  - **A printed year must agree.** When the name carries a year and the law's title prints one, the two must be
    equal. "Family Courts Act of 1964" no longer resolves to the AJK Family Courts Act 1993. "Representation of the
    People Act, 1976" (264 citations; not held) no longer reaches the 1957 Act, "Sindh Civil Servants Act, 1973"
    (not held under that title) no longer reaches the Housing Foundation Act 2005, and "Evidence Act, 1872" no
    longer reaches the Indian Museum Act 1887.
  - A title that prints no year is still accepted ("Pakistan Penal Code, 1860" → the Pakistan Penal Code). The
    reprint fallback, which drops the year, keeps the same year rule.
- Result, the SC judgments relinked under D-126 and D-127 (`nizam.judgment_links/2`, 53,091 statute citations):

  | | 22 Nov (/1, generic plans) | 23 Nov, custom plans | 23 Nov, + D-127 |
  |---|---:|---:|---:|
  | Resolved | 41,960 | 38,853 | 36,034 |
  | Law not held | — | 6,647 | 7,457 |
  | No law named | — | 2,437 | 6,554 |
  | Unit not found | — | 5,154 | 3,046 |

  The 22 Nov figure included links that resolved only because the title filter did not filter (D-126), and the
  guesses above. A random sample of 40 resolved links read 40 correct. Relinking 207 judgments in reverse order
  now changes none of them. The golden citation check is unchanged: 581 queries, 580 correct, 0 wrong.
  - Misses that remain and are honest:
    - practitioner abbreviations with no recorded alias (NAB Ordinance, STA 1973, ITO 2001, ROPA, NRO, COCA,
      CSA). Aliases grow only from evidence a person reads (PRECEDENT-MODEL §4.1);
    - spellings the title search does not join ("Sindh Rented Premises Ordinance, 1979" against the held "Sind";
      "Qanoon-e-Shahadat" against "Qanun-e-Shahadat").

    Both are an alias slice, not a guess.
- Why: a citation linked to the wrong law is worse than one left unresolved (docs/04 R0, INV-1). Through "cases on
  this section" it puts a judgment under a provision it never read.
- Where: nizam/storage/citations.py (`_KIND_ONLY`, `_YEAR`); nizam/workers/judgment_links.py; tests/
  test_citation_guesses.py. A26's resolved figure is now 36,034 of 53,091.

### D-126 · 2026-11-23 · Every connection plans each statement for its own parameters (pg_search is not exact under a generic plan)
Area: L2 storage, linking, L3 (nizam/storage/db.py) · Status: standing
- Decision: `dsn()` sets `plan_cache_mode = force_custom_plan` on every connection the package opens: workers,
  readers, retrieval and the API pools.
  - **Found** relinking the judgments for D-125. The statute links resolved 41,940, against 41,960 the day before,
    with no change to the linker's statute code. Relinking 207 judgments in reverse order changed 4 of them.
  - **Cause:** psycopg prepares a statement on the server after five executions, and Postgres may then reuse a
    generic plan. Under a generic plan, pg_search 0.25.6's operators are not exact:
    - the match-all title search (`&&&`) stopped filtering. In the linker's own order, from the 26th judgment,
      "Pakistan Penal Code" put the Constitution first, so every s.302 PPC citation of that run (952) went
      unresolved;
    - "Section 4 of the Act. Finally" was linked to Article 4 of the Constitution;
    - run directly, the same query failed with `unrecognized node type`.

    The resolver caches each (law, label) for a run, so one bad lookup spread to every later citation of that
    section, and which lookup went bad depended on the order.
  - **Measured** (302 printed law names, three passes in one transaction):

    | Parallel workers | Plan cache | Result |
    |---|---|---|
    | 2 | auto | error (`unrecognized node type`) |
    | 0 | auto | error (`unrecognized node type`) |
    | 2 | force custom | 0 titles unstable; "Act. Finally" matches nothing |
    | 0 | force custom | 0 titles unstable; "Act. Finally" matches nothing |

    A first reading blamed parallel workers, and a serial wrapper was tried. The table shows parallelism is
    irrelevant: the serial run still lost s.302 PPC. The wrapper was removed.
  - **Checks:** a test makes many varied title lookups on one connection, then asserts "Act. Finally" matches
    nothing and s.302 PPC resolves to the Pakistan Penal Code. The judgments were relinked under the fix.
- Why: a citation resolved to the wrong law is the worst failure the citation path has (docs/04 R0). Planning each
  statement costs well under a millisecond here. The same operators carry L3's BM25 windows and citation fast path,
  so the fix belongs on the connection, not in one caller.
- Where: nizam/storage/db.py (`dsn`); tests/test_judgment_db.py. The corpus browser and the MCP database server
  (tools/) open their own connections and are not covered.

### D-125 · 2026-11-23 · One record per case: a short order and its reasons are joined by their case, not merged
Area: owner ruling, schema, L1 builder, linking, serving (docs/PRECEDENT-MODEL.md §3.3) · Status: standing
- Decision: the owner asked for item 1, "one record per case", to be built fully end to end. It corrects §3.3, which
  had a short order and its detailed reasons as "one judgment with two opinions".
  - **Kept:** one judgment per file read (D-118). A short order and its reasons stay two judgments, each with its
    own printed date. Merging them would move one file's paragraphs under the other's date partition, give the
    citations a date that is not theirs, and retire readings that are correct.
  - **What joins them is the case (0123):**
    - `judicial_case` is keyed `<court>/<type>/<number>/<year>` from the printed case line (`SC/CA/1507/2024`; no
      leading zeros). The key is built from words, never a row id, so rebuilding never breaks a stored reference
      (the INV-4 rule, read for cases).
    - `judgment_case`: the lead case, and the cases of the same type and year printed beside it ('Nos. 545 to 550
      of 2015'; ranges up to 500 are expanded, a wider one keeps its ends). A number of another type in the line
      ('and CMA No. 2382') is an application in the case, not another case.
  - **The case line is read by its own grammar** (`nizam/corpus/judgment_case.py`). It reads the lead number after
    the type's printed form, and the year that closes the list. The header parser's `case_number` and `case_year`
    differ for 44 judgments. I read all 44 and the grammar was right each time ('CMA No.1652/2013 in SMC No.16 of
    2011' is CMA 1652 of 2013, not 2011). The case line is the record, and the difference is kept
    (`header_differs`). A line with no number ('No. Nil') or no year closing it is not placed in a case, and its
    state row says which.
  - **Reasons for a short order** (`judgment_relation` `reasons_for`):
    - the court's own statement, read in the first three and last four body paragraphs: "the above are the
      reasons for our short order dated 22.4.2024", "… of even date", "… announced by us on 31.05.2013";
    - the short order's date is recorded with its basis (printed, even date, earlier in the paragraph, not
      printed);
    - a statement inside a quotation (the court quoting an earlier order) is not read;
    - the short order is linked only when the case holds exactly one other judgment decided that day, and that
      judgment's own record marks it as a short order: an opinion headed SHORT ORDER, or "for reasons to be
      recorded later".
  - **Copies** (`copy_of`): two judgments of one case whose bodies overlap at 0.90 or more (word 5-gram Jaccard), on
    the same day when both are dated. The longer body is kept. `v_shown_judgment` leaves the copy out of lists and
    search; opened directly, it names the copy kept.
  - **Case citations resolve to the case** (`nizam.judgment_links/2`): "Civil Appeal No. 984 of 2018" resolves
    when the case is held, however many decisions it has. `dst_judgment_id` is set only when the case holds one,
    and a judgment citing its own case is `own_case`. Under /1 a case with several orders was 'ambiguous', and a
    number was matched only through the header parser's fields.
  - **Readers:**
    - the judgment page carries `case`: the cases decided, the other decisions with dates as shown (D-124), the
      reasons statement both ways, and copies;
    - `GET /v1/precedent/cases/{court}/{type}/{number}/{year}` serves one case's decisions on or before `as_of`,
      and the judgments citing it;
    - precedent hits carry `case_key`, `gives_reasons` and `short_order_on`; coverage counts cases.
  - **Audit A28:** the tables are exactly the release under one builder, and relations stay inside their case and
    rule.
- Result, SC (rebuilt from the 3,105 released judgments):

  | | Count |
  |---|---:|
  | Judgments placed in a case | 3,031 |
  | Not placed: no number printed / no year read | 10 / 64 |
  | Cases (with those decided together) | 6,935 |
  | Joined-case memberships | 4,316 |
  | Reasons statements | 326 |
  | of which the short order held and linked | 18 |
  | of which dated by print / even date / the paragraph / not printed | 100 / 155 / 15 / 56 |
  | Second copies | 1 |
  | Header readings that differ (case line kept) | 44 |

  Precision, author-read: a first sample of 40 reasons statements read 38 correct. The faults were a quotation and
  "of today", and both are fixed. A fresh sample of 40 after the fixes read 40 correct, and all 18 linked short
  orders are short orders by their own words. The copy threshold sits in a gap: one pair scores 0.999 and the next
  0.52.
- Why:
  - The case is what lawyers cite and what later layers resolve to: the citator (§4.2), lineage (§3.5), and "this
    case's other orders".
  - Keying it by printed words keeps every stored reference stable across rebuilds.
  - Two dated files stay two dated facts (INV-1). A short order's printed date is the decision announced, and the
    reasons' own date is when they were given.
- Where: infra/postgres/migrations/0123_judicial_case.sql; nizam/storage/case_key.py; nizam/corpus/judgment_case.py;
  nizam/workers/{judgment_cases,judgment_links}.py; nizam/storage/judgment_read.py; nizam/retrieval/precedent.py;
  nizam/api/precedent.py; tests/test_judgment_{case,db}.py; tools/audit/criteria.sql (A28); docs/SCHEMA.md,
  docs/CORPUS-CRITERIA.md.

### D-124 · 2026-11-23 · A judgment with no usable decision date is released marked undated, never dated by a guess
Area: owner ruling, schema, L1 parser, linking, serving (docs/PRECEDENT-MODEL.md §3) · Status: standing
- Decision: the owner ruled "release the undated marked as undated". It supersedes D-118's J1 hold.
  - **Who:** a judgment that prints no decision date, or prints dates that contradict each other (two signed dates,
    or a hearing after the date read).
  - **0122:** `decided_on_basis = 'undated'`, with `undated_reason`, and `decided_on_printed` NULL.
    `ck_judgment_undated` ties the three together.
  - **The date column:** `decided_on` stays the partition key and the research-date filter, so it cannot be NULL.
    For an undated judgment it holds the **latest possible day**: the day the court's archive was first observed
    holding the bytes (`judgment_source.observed_at`). A research date before that never returns the judgment, the
    conservative reading of INV-5 for case law. That day is never shown as the decision date.
    - `v_release_judgment.decision_date` is NULL for an undated judgment.
    - The readers render "date of decision not printed", with `decided_no_later_than` and `decided_not_before`
      beside it.
  - **`decided_not_before`:** the printed date of hearing, else 1 January of the case year. A hearing date that is
    the one in conflict is not used.
  - **Links:** an undated judgment's citations are linked with no version (`not_dated`), because the text the court
    read cannot be chosen without the date. "Cases on this section" lists dated judgments first and undated ones last.
  - **Coverage:** `v_judgment_coverage` counts undated judgments in one row with year NULL. Search reports them as
    `undated`.
  - **The parser `nizam.judgment/3`:** only the files held at J1 were re-read (`--held J1`). No released judgment was
    retired. Reading those files found three reader defects:
    - a closing date line ("LAHORE / 12.02.2026") had opened a false paragraph "12", hiding the date. `_PARA` now
      refuses a number followed by a digit;
    - "22d December" was not read;
    - a hand-filled blank ("ANNOUNCED ON _14th _January, 2011") was not read.

    No released judgment had the false paragraph (checked: 0 body paragraphs opening on the rest of a date).
  - **Audit A25** now also asserts that every undated judgment's latest-possible day equals the archive's first
    observation, and that none of its links claims a version.
- Result, SC archive:

  | Of the 327 held at J1 | Judgments |
  |---|---:|
  | Dated after the reader fixes | 13 |
  | Released undated | 314 |
  | of which "no printed date" | 283 |
  | of which conflicting dates | 31 |
  | of which bounded by a hearing date | 180 |
  | of which bounded by the case year | 131 |
  | of which with no lower bound | 3 |

  Released SC judgments are now 3,105; 193 files are still held (court not resolved, no heading, J3).
  Linking the 327: 9,977 citations resolved, all `not_dated` for the undated ones.
- Why:
  - A judgment the court published is evidence of the law, so withholding it for a missing date lost precedent.
  - Guessing a date would break INV-1: a decision date is a rendered fact.
  - The latest-possible day is the only bound that is certainly true, and using it as the filter can hide a
    judgment from an early research date but can never show one before it existed.
- Where: infra/postgres/migrations/0122_undated_judgments.sql; nizam/corpus/judgment.py;
  nizam/storage/{judgment_write,judgment_read}.py; nizam/workers/{judgments,judgment_links,judgment_chunk}.py;
  nizam/retrieval/precedent.py; tests/test_judgment_{parse,db}.py; tools/audit/criteria.sql (A25).

### D-123 · 2026-11-22 · Supreme Court precedent landed end to end: courts, judgments, links to the law, search, routes
Area: owner ruling, L1/L2 schema, linking, L3, L6 (docs/PRECEDENT-MODEL.md) · Status: standing
- Decision: the owner asked to add precedent starting with the Supreme Court, "fully end to end". Built in order,
  each slice tested before the next.
  - **0118, courts and authority (D-116).** 8 courts, 5 superintendence rows, 6 jurisdictions and 7 binding rules,
    each citing its source by (observation, ordinal, unit, exact words). The migration refuses a seed whose words
    are not printed, and audit A24 asserts the same on every run. `nizam/storage/authority.py` resolves
    `Binding | NotBinding | NotRecorded` as at the research date.
  - **0119, the judgment ladder.** `judgment_source → judgment_document → judgment_block → judgment →
    judgment_opinion → judgment_paragraph`, with `judgment_lineage`, `case_type` (19 SC types, seen in the archive),
    the statute and case reference tables, and release views.
    - **A ladder of its own** (correction to D-118 §3.1, which said judgments enter by the statute ladder):
      criteria C1–C9 assert that every block of a landed observation belongs to a provision of a law, which no
      judgment is. Sharing source_observation, blob and document would have failed about ten criteria.
    - **Partitions:** judgment and judgment_paragraph are partitioned by decision date (a catch-all before 2010,
      then 2010–2027), created ahead of time.
  - **The parser `nizam.judgment/2`** (nizam/corpus/judgment.py) reads the header, opinions, printed paragraph
    numbers in sequence, footnotes, furniture and closing. The decision date comes from the closing ("Announced …
    on", "<place>, the <date>", or "Date of decision"), never from the hearing, a filename or the year folder: the
    folder is the case year, and `c.p._600_2020` was decided on 26 Jan 2023.
  - **The archive** (`scp_judgments.zip`): 3,750 files, 3,744 distinct.

    | Outcome | Files | Detail |
    |---|---:|---|
    | Released | 2,778 | |
    | Held | 520 | no printed decision date (J1) 327; court not resolved 70, mostly a separate note or an "order of the court" filed alone, or a damaged header; no heading 63; no case number (J3) 59; unreadable 1 |
    | Waiting for OCR | 438 | no text layer 423, a thin layer 8, Urdu 7 (the D-114 lane) |
    | Duplicate (J6) | 8 | |

    Check: of 248 parsed files whose names carry a date, 188 agree. Most of the rest name a later release of
    reasons, not the decision. The printed words are stored with every date (`decided_on_printed`).
  - **Links (D-119), as built:**
    - The grammar moved to `nizam/storage/citations.py`, not `nizam/shared/`. `.importlinter` contract 3 keeps
      domain logic out of shared/, and storage is importable by both L3 and the workers.
    - **0121:** a bare citation ("section 497(2)") takes the law the judgment last named for the same kind of unit,
      recorded `inherited` with the citation it came from. In a 150-judgment dry run this lifted resolved citations
      from 1,733 to 3,328 of 3,800. No default law is assumed.
    - The version is read through `operative_provision` at the decision date (INV-5). Most of the codes are served
      only from capture because an amendment is undated (the PPC, for one), so most links are `not_dated`. The
      reader says "the text this court read is not held" rather than showing today's text as the court's.
  - **0120, search:**
    - BM25 on the partitioned `judgment_paragraph` (pg_search 0.25.6 propagates a parent's index; tested on this
      build).
    - `judgment_chunk`: offsets into paragraphs, with the CPU bge-m3 generation's sign bits and HNSW. One table:
      correction to D-121's "partitioned", since one court is not yet large.
    - `nizam/retrieval/precedent.py` fuses BM25, dense and "judgments citing the provision the question names"
      by RRF (k = 60), one hit per judgment.
    - Each hit carries its binding status for a named forum, the law it read with whether that text is still
      operative, and the coverage searched. It is discovery, not an answer, and passes no gate (INV-2).
  - **Routes:** `/v1/precedent/search`, `/v1/precedent/judgments/{id}`, `/v1/law/provisions/{id}/judgments`,
    `/v1/precedent/authority`, `/v1/precedent/coverage`.
  - **Audits A25–A27:** the judgment ladder, the links, and the chunks are each exactly the release.
- Not done, and why:
  - **The 8B GPU space for judgments** (D-121): the Kaggle top-up reads `chunk` only and needs a judgment input
    path.
  - **Treatments, invalidations, the citator and proposition review** (D-117, docs/06 §5).
  - **Party display redaction rules:** `parties_display` is NULL everywhere, and party names are never served or
    searched (D-122).
  - **Short orders and detailed reasons** are separate judgments per file, linked to nothing yet. D-118 calls them
    one judgment with two opinions; merging them needs a case-identity rule.
  - **A precedent stratum in the golden set** and a calibrated precedent gate.
  - **The 438 scans.**
  - **The mobile screens.**
- Why this order: each slice reads the one before (docs/PRECEDENT-MODEL.md §7). The SC first, as the owner asked
  and as §7 recommends: the cleanest archive, the only one with source URLs, and the most binding court held.
- Where: migrations 0118–0121; nizam/corpus/judgment.py; nizam/storage/{authority,citations,judgment_write,
  judgment_read,judgment_linking}.py; nizam/workers/{judgments,judgment_links,judgment_chunk}.py;
  nizam/retrieval/precedent.py; nizam/api/precedent.py; tests/test_{authority,judgment_parse,judgment_db}.py;
  tools/audit/criteria.sql (A24–A27); logs in E:/nizam-data/acquire/judgments-sc-*.log.

### D-122 · 2026-11-22 · Precedent coverage is shown with every answer; party names are redacted by category; no judge analytics
Area: serving, security (docs/06 §5.1, docs/11) · Status: standing
- Decision:
  - `v_judgment_coverage` (court × year: held, source, last crawl, gaps) travels with every precedent answer and
    `AuthoritySignal`. "No adverse treatment found" is always qualified by it.
  - `parties_display` is redacted for sensitive categories (family, sexual offences, minors, medical). Each category
    cites its statutory basis from the corpus, or is marked as product policy.
  - Party names are not a search key.
  - Judges are recorded for bench composition and authorship only: no per-judge outcome statistics, no prediction.
- Why:
  - The inventory is very uneven: Sindh's 55,075 files hold no text, and FCC, IHC, BHC, FSC, AJK and GB are absent.
    An absence of evidence over that coverage must never read as "good law".
  - docs/06 forbids predicting a judge.
- Where: docs/PRECEDENT-MODEL.md §6.2–6.3.

### D-121 · 2026-11-22 · Judgment chunks and vectors are their own tables, in the same embedding generations
Area: schema, retrieval (docs/03 §3, docs/04 §6) · Status: standing
- Decision:
  - `judgment_chunk` holds offsets into `judgment_paragraph.text`, partitioned by `decided_on`. It carries its own
    bge-m3 `bit(1024)` column, plus `judgment_chunk_embedding_gpu` (`bit(4096)`). Each space has its own HNSW and
    BM25.
  - The encoders and generations are the statutes' own, so one query vector searches both.
  - Citations above L2 are judgment paragraphs (INV-4).
- Why:
  - `chunk` is defined against `provision_version`, and A20–A22 assert it equals the statute release.
  - A judgment span must never pass the statute gate; precedent mode needs its own calibrated gate.
  - Date partitions prune.
- Where: docs/PRECEDENT-MODEL.md §6.1.

### D-120 · 2026-11-22 · Law-reporter reprints are not landed; their citation is kept as an identifier
Area: corpus, owner delegation (nizam-corpus copyright line, docs/04 §R0) · Status: standing
- Decision:
  - A judgment file that opens with a reporter citation and editorial headnote is recorded as a non-authoritative
    copy and not landed. Detection: a reporter citation in the first lines plus at least four `---` separators,
    with a person reading the borderline cases.
  - Its citation ("2014 MLD 446") becomes a `reporter_ref` alias on the judgment once the official copy is held, and
    the official copy is recrawled.
- Why: headnotes are the reporter's copyright. A 150-file first-page sample found them in 0 SC files, 12 LHC files
  and 13 PHC files, roughly 900 files across both High Courts.
- Where: docs/PRECEDENT-MODEL.md §5; docs/DEFERRED-SOURCES.md item 7 (measured 22 Nov).

### D-119 · 2026-11-22 · Judgments link to the provision version in force on the decision date, by one shared citation grammar
Area: linking (docs/03b §6, D-097, D-108) · Status: standing
- Decision:
  - **`judgment_statute_reference`:**
    - a derived table, linker `nizam.judgment_links/1`, rebuilt from the release, with audit A24;
    - it resolves each printed citation ("S. 302(b) PPC", "u/s 497 Cr.P.C.", "Article 199") to the deepest unit and
      to **the version valid on `decided_on`** in the deciding court's territory;
    - it records `role` (charge, quoted, challenged, interpreted, cited) and the resolution state;
    - `amended_since` and `repealed_since` are computed at read time.
  - **`judgment_case_reference`** resolves cited cases by (court, case number, year) or a reporter alias.
  - **`judicial_invalidation`**, lawyer-verified, feeds `legal_edge` `invalidated_by`, effective from the date the
    decision sets (Art. 203D(2)(b)) and held back while an FSC appeal lies (203D(2) proviso).
  - The grammar and aliases of `nizam/retrieval/citations.py`, and the title resolver of `nizam/storage/linking.py`,
    move to `nizam/shared/` so that L3 and the L1/L2 worker share one copy.
- Why:
  - A court reads the law as it stood when it decided. A judgment on a since-substituted section must say so.
  - Two citation grammars would drift.
  - A worker importing L3 breaks the layer rule.
- Where: docs/PRECEDENT-MODEL.md §4.

### D-118 · 2026-11-22 · A judgment has opinions; paragraphs cite by printed number; no decision date, no landing
Area: schema (docs/03 §2.5, docs/06 §5.2) · Status: standing; the J1 hold ("no decision date, no landing") Superseded by D-124
- Decision: judgments enter by the statute ladder (observation → blob → document → text_block). The new tables:
  - **`judgment`** (partitioned): `court_code`, `seat`, `decided_on` with its printed basis, the case type and
    number, the jurisdiction invoked, the bench kind and size, `reported_flag`, and a neutral citation only when
    printed.
  - **`judgment_opinion`:** judgment of court, majority, concurring, dissent, short order, detailed reasons. A short
    order and its later reasons are one judgment.
  - **`judgment_paragraph`:** `printed_no` or NULL; the citation falls back to the page, never an ordinal (INV-1).
  - **`judgment_translation`** for official Urdu translations.
  - **`judgment_lineage`** (appeal, revision, review; affirmed, reversed …).
  - **`case_type`.**
  - **Gates J1–J8.** A judgment with no printed decision date is held, never dated from the upload or the filename.
- Why:
  - docs/06 filters evidence by opinion, but docs/03 had no opinion table.
  - The SC archive holds short orders and detailed reasons as separate files of one case.
  - A synthetic paragraph number is a generated citation.
- Where: docs/PRECEDENT-MODEL.md §3.

### D-117 · 2026-11-22 · Two treatment vocabularies (case and provision); appeal history is lineage, not treatment
Area: schema, L5 (docs/03 §1.1, docs/06 §5) · Status: standing · Supersedes docs/03 §1.1's `treatment` enum
- Decision:
  - **`case_treatment`:** cited, applied, followed, approved, explained, distinguished, doubted, disapproved,
    overruled, per_incuriam. Polarity is a fixed map, not a stored column.
  - **`provision_treatment`:** cited, applied, interpreted, upheld, read_down, struck_down, declared_repugnant.
  - "Affirmed" and "reversed" move to `judgment_lineage`.
  - Negative treatments, invalidations and reversals display only when `lawyer_verified`.
- Why:
  - docs/03 (7 values) and docs/06 (11 values) conflicted. docs/06 owns treatment (docs/04 §6.5).
  - A case's appeal outcome and a later court's view of its reasoning are different facts.
  - A stored polarity could contradict its treatment.
- Where: docs/PRECEDENT-MODEL.md §2.

### D-116 · 2026-11-22 · Courts are data; whether a decision binds is a dated rule read from the Constitution's text
Area: schema, serving (docs/03 §1.1, docs/04 §6.1, docs/06 §2.1) · Status: standing · Supersedes docs/03 §1.1's `court` enum
- Decision: the tables are `court`, `court_seat`, `court_alias` (observed headers only), `court_jurisdiction`,
  `court_superintendence` and `authority_rule`.
  - **`authority_rule`** stores binding rules only. Each has a validity under EXCLUDE (no overlaps), and exactly one
    source: a provision version or a judgment paragraph.
  - **Seeds, read from served records:**
    - Art. 189 of the 2016 copy: SC binds all courts.
    - The 27th Amendment Act s.34 (commenced 2025-11-13), substituting Art. 189: FCC binds all courts including the
      SC (189(1)), and the SC binds all courts except the FCC (189(2)).
    - Art. 201: a High Court binds its subordinate courts, subject to Art. 189, with Art. 203 for "subordinate".
    - Art. 203GG: the FSC binds the High Courts and their subordinate courts, subject to 203D/203F.
  - **Gaps:** a gap between dated texts is filled only from amendment records.
  - **Not recorded:** the AJK and GB courts (their constitutions are not held) and the bench rules (case law).
  - **The resolver** returns `Binding | NotBinding | NotRecorded`, read as at the research date.
- Why:
  - The enum had no FCC, no AJK or GB courts, and no dates. docs/04 §6.1 marked it stale.
  - Art. 189 changed on 13 Nov 2025, so whether an SC decision binds depends on the date.
  - Every rule must be replayable from a record (INV-1, INV-3).
- Where: docs/PRECEDENT-MODEL.md §1. Version ids of the seeds are in §1.3.

### D-115 · 2026-11-22 · A notification with no numbered paragraphs is one citable unit, "Notification"
Area: L1 segmentation, L2 schema and serving (docs/02 §5, docs/03 §2, docs/03b §3) · Status: standing
- Decision: the owner asked for the leftovers of D-113 to be fixed ("fix these also"). 307 regulator texts were
  blocked because their operative words sit in one unnumbered paragraph: an SRO or SECP notification ("In exercise
  of the powers conferred by ... is pleased to direct that ..."). The segmenter read that paragraph as preface, so
  no unit held law.
  - **New provision kind `notification`** (migration 0117). Its label is the word the page prints over it,
    "Notification", never a number. The citation renders as "<title>, Notification" from records (INV-1); the path is
    `<prefix>.notif_Notification`. Its depth is 3, a section's grammar rank.
  - **New profile `notification-v1`** = default + two rules:
    - `gazette_masthead_part`: the Gazette's "PART II / Statutory Notification(s)" masthead is a printing head, not
      a Part of the law. Its blocks become preface and its children are lifted to the root unchanged.
    - `notification_unit`: from the number line ("S.R.O. 123(I)/2024", "No. ...") or a NOTIFICATION heading
      through to the formula's paragraph end, the closing file number or the signature, the paragraph is one unit;
      the law's numbered items (clauses, sub-paragraphs), and every unit that is not a schedule, form, appendix or
      annexure, go under it.
  - It applies only to documents pinned to `notification-v1` before their first parse (`pin_segmentation_profile.py
    --observations`). No released law changes, because released laws replay under their own pin.
  - Serving code knows the kind: chunking, unit search, the Kaggle embed inputs, assembly, `library_read`
    (`render_citation`), the mobile `law_units`.
- Result, 22 Nov 2026:
  - Of the 292 notification-shaped texts the rule fires on 238; preflight under the profile predicted 240 clean. One
    hidden draft was excluded and one more is not a law, so 238 were landed (`recrawl-2026-11-22/1`, observations
    15450–15687) and all 238 passed the gates (10,572 → 10,810). 237 carry one `notification` unit; the 238th,
    the SECP Unit Linked Products Fund Rules 2015, has rules, and the rule stands aside.
  - D-113's first-page sweep, run over the 238, found two more drafts behind ordinary titles: doc 11711 (SRO
    1247(I)/2017, "objections or suggestions ... within seven days of placement of the draft") and doc 11796 (S.R.O.
    1349(I)/2025, "DRAFT AMENDMENTS ... comments, if any"). They are recorded `source_not_law` (0116;
    `tools/record_not_law.py`, now idempotent). Mentions of "draft", "circular" or "guidelines" inside operative
    text were read and are law. **Released: 10,808** (236 notifications and rules).
  - The status and date recorders (record_enacted_dates, record_commencement, record_status, then
    apply_instrument_metadata) are not part of `post_replay_sequence.sh` and had not run since D-113. Run now: 154
    enactment dates and 18 commencements recorded, 456 laws presumed in force under the owner presumption (16 Nov),
    D-113's 230 among them. **Current: 8,242 → 8,700.**
  - Retrieval: the chunk table follows the release (A20); 18,154 chunks were re-cut or added (split-document
    re-materialisation re-cuts about 17.6k each run) and embedded on the CPU; the 8B GPU vectors are topped up on
    Kaggle (A22). Links rebuilt; golden sets 1–10 rebuilt with 0 problems.
  - That Rules text carried a false section: page 4 prints "... set out as Annexure 2. A life insurer may ...", the
    text layer breaks after "Annexure", and "2." opened a section "2" holding the rest of rule 7. It was held, read
    from the page (`tools/evidence/annexure-wrap-2026-11-22/`, a text reading joining the wrapped line), replayed
    (sections 16 → 15, S7 0) and re-verified. A scan of all 238 for a section opening on a continuation found no
    other.
- Not done here, and why:
  - The wrapped-reference guard (`_REFERENCE_LINE_END`) does not list "Annexure", "Schedule", "Form" or
    "Appendix" as reference nouns. Adding them changes the default profile's output, so it waits for a new profile
    and a corpus-wide count of the docs it would change. Open question.
  - Still blocked from the drops: 88 texts with repeated section numbers (S7) need a decision per document against
    the page; about 65 have no structure the rule recognises; 6 FBR 2026 consolidations need a rule for a newer
    consolidation of a law already served, which docs/03 does not have.
- Why one unit, not one unit per sentence or a synthetic "paragraph 1":
  - The notification is the citable act. Gazette practice cites "Notification No. S.R.O. ..." for the whole text.
  - A number the page does not print is a generated citation (INV-1). A label the page prints is not.
- Where:
  - nizam/corpus/segment.py (`gazette_masthead_part`, `notification_unit`, profile `notification-v1`, path
    abbreviation `notif`); infra/postgres/migrations/0117_notification_unit.sql;
  - nizam/storage/chunking.py, unit_search.py, library_read.py; nizam/retrieval/assembly.py;
    tools/kaggle/embed_inputs.py; tools/pin_segmentation_profile.py (`--observations`);
    apps/mobile/lib/domain/law_units.dart;
  - tests/test_notification_unit.py; tools/evidence/hold-annexure-wrap-2026-11-22.sql; tools/record_not_law.py.
- Process rule: `tools/post_replay_sequence.sh` gains step 4a3, the status chain (enacted dates → commencement →
  statutory repeals → status → apply repeals → apply metadata), before 4b refreshes serving. A landing can no longer
  release laws without the owner's presumption of force.

### D-114 · 2026-11-22 · Scans are read by Google Document AI and released where a second engine agrees
Area: owner ruling, L1 lane E4 (docs/02 §4) · Status: standing · Supersedes D-034 (scans not landed)
- Decision: the owner asked for the held scans to be read with Google Document AI ("use this for quick correct ocr of
  docs and release further quickly") and gave the processor: Document OCR, region us,
  `projects/189384242594/locations/us/processors/537ddf134d0c28d0`. D-034's rule that scans are not landed ends.
  - **Reader.** `nizam/corpus/ocr_docai.py` produces lane E4's `ExtractedDocument` unchanged in shape:
    - each paragraph is a block, in PDF points of the original page;
    - each block's confidence is its tokens' mean, and the document's mean is token-weighted;
    - the metadata keys `verify_ocr` reads keep their meaning;
    - the extractor names the processor version, so a newer model is a new revision.
  - **Requests.** PDFs are cut into 15-page parts, the online limit read from the limits page on 22 Nov 2026. Every
    response is kept gzip-compressed under `E:/nizam-data/ocr/docai/<version>/<sha256>/`. A re-run, or the landing
    after a preflight, reads the stored response and never pays for the page twice.
  - **Credentials.** Application Default Credentials. Only the PDF bytes and the processor name leave the laptop.
  - **Run.** `nizam.workers.ocr --engine docai` (threads, because it is network-bound); `pipeline.sh` takes
    `OCR=1 OCR_ENGINE=docai`.
- **Verification: an independent second reader.** Tesseract reads every scan on the laptop
  (`tools/acquire/second_read.py`, the existing `ocr_pdf` unchanged). `nizam/corpus/crossread.py` compares the two
  readings page by page:
  - character recall and precision over letters and digits, both at least .90;
  - ordered word-bigram precision of the release reading, at least .70, which catches interleaved columns.

  A page the second reader could not read (under 80 characters) does not vote. `verify_ocr` (v7) adds the cross-read
  as a problem for every Document AI revision without a page-read assertion. `preflight_segment.py --ocr docai
  --second-read DIR` predicts the same before landing. Every other gate is unchanged: confidence .70, legal-token rate
  .25, 40 words a page, S7, contents, leakscan.
- **Thresholds.** They are provisional. They were fixed before any Document AI output was seen, from Tesseract's
  measured confidence on the first AJK sample (.88–.95). They are recalibrated once, on dev pages that were page-read,
  and the change is logged. They are never tuned per document. A page that disagrees is named for a page read, not
  averaged away.
- Why:
  - Lane E2's acceptance is two independent libraries agreeing over the same bytes. Two OCR engines that share no
    model agreeing on a page is the same kind of evidence.
  - Page-reading every page as D-076 did does not scale to 1,000+ laws. The D-076 rule stays for any page the two
    engines dispute.
  - Not measured: Document AI's own accuracy on these scans, and its price. The pricing page did not load on
    22 Nov 2026, so no price is quoted here.
- Where:
  - nizam/corpus/ocr_docai.py, nizam/corpus/crossread.py, nizam/workers/ocr.py (`--engine`), nizam/workers/verify_ocr.py
    (`_crossread`, VERIFIER 7);
  - tools/acquire/second_read.py, tools/acquire/preflight_segment.py (`--ocr`, `--second-read`), tools/recrawl/pipeline.sh;
  - tests/test_ocr_docai.py, tests/test_crossread.py.

### D-113 · 2026-11-21 · The held-back regulator sources: the binding text-layer instruments landed; drafts, guidance and scans not
Area: owner ruling, L1 acquisition and release (docs/02 §2, §8; docs/DEFERRED-SOURCES.md items 1–5) · Status: standing
- Decision: the owner said "add data of these all as much as u can". This takes up D-100's held list, apart from
  judgments, which wait for their own pipeline. Five drops were taken; the bytes come from the September zips in
  E:/nizam-data:
  - FBR codes;
  - FBR Customs SROs (the copy in the Peshawar bundle, whose manifest names each file's URL);
  - SECP;
  - PSX;
  - GB.

  Each landed file carries:
  - its official URL from the drop's manifest (`canonical_url`);
  - its zip member and scraper run (`source_metadata.drop`);
  - the date the scraper fetched it (`fetched_at`), which opens provision validity.

  FBR, SECP and PSX land as `pk-federal`, as the Ministry of Law's DRS files did. Their hosts join the allow-list.
  - **The two GB laws** (Civil Servants Act 2011; Government of Gilgit-Baltistan Order 2018) have no manifest. They
    were fetched live from gilgitbaltistan.gov.pk on 21 Nov and are byte-identical to the zip, so they carry that URL.
- **What counts as law** (the recommendations in DEFERRED-SOURCES, taken):
  - **Landed:** Acts, Ordinances, Rules, Regulations, SRO notifications, and the PSX Rule Book.
  - **Not landed:** SECP circulars, guidelines and directives, and every other PSX file (notices, forms, policies,
    schedules of charges). These are regulator guidance, not legislation.
  - **Drafts are never law.** 172 drafts were left out on their titles before landing.
  - **Held laws are left out** on the 19 Nov comparison. A "possible match" counts as held unless its title amends
    something, because an amending instrument is a different instrument from the one it amends.
- **The same file twice, or an older dated consolidation:** only the newest of each instrument is staged
  (`tools/acquire/stage_drops.py`).
- **The gates were unchanged:** stage, then `preflight_segment.py`, then `select_landing.py` (text layer; clean or
  leaky), then `land_missing.py --staged`, then `tools/recrawl/pipeline.sh`.
  - **251 landed:** 9 FBR, 27 Customs SROs, 213 SECP, 2 GB. PSX's Rule Book was blocked: its rules repeat labels
    (S7 = 20).
  - All 251 passed verification: 248 character-perfect, the worst precision .99917, and none for text review.
  - All 251 segmented and were released; the release rose from 10,342 to 10,593. Two fixes were needed on the way:
    - **Extraction:** a media box with a fractional origin ('[0 .02 598.3 846.72]') made PyMuPDF refuse the crop box,
      and 29 SROs failed. Boxes agreeing within a point are now treated as the same page (`nizam/corpus/extract.py`).
      Only files that used to fail can change.
    - **Staging:** "Amended upto" no longer reads as an amending instrument.
- **Not law after all: 21 taken back out** (migration 0116 `source_not_law`). A first-page sweep of every landed law
  found:
  - 19 drafts published for consultation, whose titles do not say so ("The following draft of the X Regulations …
    proposed to be made … objections or suggestions");
  - one SECP circular;
  - one press release.

  Each is recorded with the printed words and their block, and `v_release_instrument` leaves them out. A hold would
  have been untruthful, and 0065 needs an authoritative counterpart the corpus does not have. The release stands at
  10,572: +230 laws.
- **Kinds.** The title outranks the catalogue, so amending SROs were typed `rules` or `regulation`, and one
  `constitution`. 62 were corrected to `notification` or `sro` by 0101 assertions, each quoting the printed
  NOTIFICATION or S.R.O. line (`tools/record_drop_kinds.py`). A principal "X Regulations, 2015" made by SRO keeps
  its kind.
- **Left (docs/DEFERRED-SOURCES.md, updated):**
  - **Scans:** 266 in these drops (FBR 7, Customs 11, SECP 248) plus the 16 GB Act scans, and the earlier 874 AJK
    and 151 GB scans.
  - **Text-layer files the segmenter cannot yet structure:** 410.
    - 290 are notifications with no numbered sections. Their operative lead-in falls outside every unit, so they need
      a rule serving an unnumbered notification as one unit with its paragraphs.
    - The rest repeat labels (S7) or fail evidence.
  - **The six FBR 2026 consolidations of laws held** (Customs, Sales Tax, Federal Excise, the Income Tax Ordinance
    twice, the Finance Act 2026). These need the newer-consolidation rule docs/03 lacks.
- Where:
  - tools/acquire/stage_drops.py, select_landing.py (drop provenance); tools/recrawl/land_missing.py;
  - nizam/workers/recover_acquisition.py (allow-list); nizam/corpus/extract.py;
  - infra/postgres/migrations/0116_source_not_law.sql; tools/record_not_law.py, tools/record_drop_kinds.py;
  - E:/nizam-data/acquire/drops-2026-11-21/ (staged, preflight, select and excluded files per drop).

### D-112 · 2026-11-21 · ADR-1d after reranking: the CPU generation keeps its sign bits
Area: architecture (ADR-1d, D-005), L2 vectors, L3 dense generator · Status: standing; settles D-098 item 4 for bge-m3
- Decision: the CPU generation (bge-m3, `bit(1024)` in `chunk.embedding`) keeps binary storage. Measured after
  reranking, as D-005 requires, binary costs 0.6 NDCG@10 points, inside the 2-point allowance.
- **The float arm is exact.** D-098 stored no float vectors, and a sample would only approximate float retrieval, so
  the whole corpus (1,132,254 chunks) was re-embedded in float on a Kaggle T4.
  - `tools/kaggle/embed_kernel.py` gained `KG_KEEPFLOAT=1` and `KG_REV`. The revision is pinned to the generation's
    own commit 5617a9f6, because the kernel had embedded the hub head before.
  - It took 1.52 h. It returns, per dev question, the served window (900 chunks) nearest by float cosine and by
    Hamming on the same vectors' sign bits.
  - The questions went without gold (`evals/adr1d_export.py`). A smoke run proved the space first: 0.99998 bit
    agreement with `chunk.embedding` over 20,000 chunks.
- **The two arms** (`evals/adr1d_eval.py`, dev, 276 answerable questions):
  - **binary** is the served `dense_units` over the stored bits;
  - **float** is the float window collapsed by the same rule.

  Both pass serving's INV-5 gate, keep 50 units, and are reranked as served on the CPU profile (int8 mMiniLM over the
  first 10 units at 800 characters).
  - **Same space:** the run's Hamming window against an exact scan of the stored bits has Jaccard .985 on average
    (min .946, 28 questions). The few differences are passages that replays added, embedded by the CPU int8 encoder.

  | (float − binary, paired bootstrap) | float | binary | difference [95% CI] |
  |---|---|---|---|
  | dense NDCG@10 | .451 | .416 | +3.5 [+1.1, +6.0] |
  | dense recall@50 | .750 | .703 | +4.7 [+1.5, +8.2] |
  | **reranked NDCG@10** | .461 | .455 | **+0.6 [−1.7, +2.9]** |
  | reranked MRR@10 | .437 | .434 | +0.3 [−1.9, +2.6] |
- **Reading it honestly.**
  - Before reranking, the sign bits cost real ranking quality, a significant 3.5 NDCG and 4.7 recall@50 points,
    confirming D-098's dense-only finding.
  - The reranker recovers almost all of the NDCG. The rule is met on the point estimate, but the interval's upper end
    (2.9) does not exclude a cost above 2 points.
  - The recall@50 loss stays in the dense generator. In serving it is partly carried by the hybrid's lexical side,
    which this dense-only arm leaves out.
  - docs/10 §7.1 also asks that "Recall@50 passes" (≥ 0.90). The CPU profile misses it with float vectors too: dense
    alone .750, the served hybrid .764 on dev (D-098). That is a limit of the CPU profile, not of the storage. Binary's
    own share is the 4.7 points above.
  - Consequences: binary stays, and the halfvec fallback is not built. If the CPU reranker's depth grows beyond 10
    (a faster host, D-101), the check re-runs: the deeper the reranker reads, the more the dense window's recall
    matters.
- **The GPU generation (Qwen3-Embedding-8B) is not re-measured here.**
  - Its served path already re-ranks the Hamming window against stored halfvecs at precision (`rescore_dims`, 0112).
  - Dense-only, its sign bits lost nothing (D-099: bits r50 .968 against float .940).
  - A float re-embedding of the corpus would take about 11 GPU-hours. It is recorded as not measured, and low risk.
- Where: evals/adr1d_export.py, evals/adr1d_eval.py, evals/results/adr1d-dev-2026-11-21.json;
  tools/kaggle/embed_kernel.py, tools/kaggle/kg.sh (KG_KEEPFLOAT, KG_REV); run nizam-embed-run-adr1dfull (account 2),
  data /mnt/e/nizam-data/embed/{ds-adr1d-20261121, out-adr1dfull}.

### D-111 · 2026-11-21 · Gate refit on the repaired corpus (gate v2 rule, unchanged)
Area: L3 gate (docs/04 §8), evaluation (docs/10) · Status: standing; supersedes D-106's calibration only, not its rule
- Decision: the gate is refitted, because D-109 shifted the Urdu questions' CPU features and D-110 changed the corpus
  and the bundles. Nothing in the rule changed: gate-rule-2026-11-20 and its D-106 addenda, the same F1–F4 candidate
  sets, leave-one-family-out, the 0.95 target with the 0.90 fallback. Dev was fitted and test scored once.
- **Features were recomputed for all 500 cases in all three modes.**
  - The D-110 replays and post-replay re-materialisations re-identify units. The 8B vectors of the 17,635
    re-chunked passages were topped up on Kaggle (A22), and 2,300 GPU pairs with new passage text were scored by
    Qwen3-Reranker-8B (`rerank/out-rrg3-8b`).
  - Two runs writing one features file each keep only their own modes, so the GPU modes ran into their own file
    and were joined by `evals/merge_gate_features.py`.
- **The fit** (dev, out of fold) chose the same sets as D-106:

  | mode | set | τ (was) | precision | pass | sufficient (was) |
  |---|---|---|---|---|---|
  | CPU | F4 | .766 (.761) | .951 | 101 | 177 (173) |
  | GPU | F1 | .744 (.671) | .957 | 253 | 261 |
  | unreranked | F2, the .90 fallback | .792 | .905 | 21 | — |
- **Test, scored once with the frozen calibration (gate v2 → now):**

  | mode | passed | answered precision | coverage of answerable | wrong passes |
  |---|---|---|---|---|
  | GPU | 166 → 162 | .940 → .944 [.898, .971] | .948 → .925 | 10 → 9 |
  | CPU | 55 → 55 | .909 → .909 [.804, .961] | — | — |
  | unreranked | 18 → 20 | 1.0 → 1.0 | — | 0 |

  - GPU unanswerable recall is .952 (L3 scope 1.0). Strict abstention precision fell from .69 to .61: the higher τ
    abstains on four more answerable questions.
  - All of these moves are inside the intervals. The CPU gate still misses 0.95 on test by its point estimate (open
    since D-102).
- Where: nizam/retrieval/gate_calibration.json; evals/results/gate-features-{dev,test}-2026-11-21.json,
  gate-fit-dev-2026-11-21.json, gate-{dev,test}-2026-11-21.json; evals/gate_features.py (GPU_SCORES gains
  ds-gate-y / out-rrg3-8b), evals/merge_gate_features.py.

### D-110 · 2026-11-21 · Retrieval close-out, part 1: conflicts, coverage per sub-question, lead-in scope, held room rejected, footnote false sections repaired
Area: owner ruling, L3 assembly (docs/04 §7), L2 links (docs/03b), L1 corpus repair · Status: standing
- Decision: the owner asked to "do till before held back sources … fix everything fully end to end and check too". The
  order was the plan given beforehand: conflicts, room for every gated unit, Explanation scope, corpus repairs,
  sub-questions, the gate refit, ADR-1d, then the close report. This entry covers the first five; D-111 and D-112
  cover the rest.
  1. **Conflicts in the packet** (docs/04 §7 `ConflictSet`). When one admitted item says "notwithstanding" another
     admitted item, or is "subject to" one, `GroundingContext.conflicts` records
     `{prevails, over, kind, said_by}`, read from `provision_reference`. It carries ids and the edge only. The words
     are the units' own and are rendered from their records (INV-1), so no composed "section N" string is built.
     (The first draft built one; it hard-coded "section", which is wrong for Articles.)
     - **Read on dev.** A fixed-seed sample of 12 recorded conflicts was read against the law: 10 were right. The 2
       errors were one pattern, "shall be subject to the penalties provided in sections 494 and 495 of the Pakistan
       Penal Code" (Parsi Marriage Act s.5, Special Marriage Act s.16). That is a liability, not precedence, so
       linker `nizam.links/9` reads it as `refers_to`. After the rebuild, GPU dev records 183 conflicts in 91 of
       276 cases (CPU: 144 in 75).
  2. **Room held for every gated unit: measured and rejected.** The variant held room for every governing unit of up
     to 8,000 characters ahead of the additions. On dev, GPU results did not change at all. On CPU, one necessary unit
     (S1-P09) and one text check (S5-U04) were lost, because the additions pushed out carried more than the low-ranked
     units let in. The case that motivated it (S5-C02) did not change. `select()` admits in priority order, as before.
  3. **Lead-in scope** (`linking.lead_in`, linker `nizam.links/8`). "In this Part, unless the context otherwise
     requires,—", or an "Explanation.—For the purposes of this section,—", is printed as its own sibling before the
     definitions it governs. A definition whose own words name no scope now takes the scope from that lead-in. The walk
     skips sibling definitions, never other words. This closes the open question from D-108's one test error: Punjab
     Labour Code s.404's "company" was whole-law and is now scoped to s.404. After the rebuild: 469 definitions
     scoped to a division, 69,696 to the law, 1,865 to the unit.
  4. **Footnotes that opened false sections: seven laws repaired.** The notes printed below a page rule were read as
     law, and a note number opened a section:
     - CrPC "1327-A" held s.4(1)(i)–(w) and s.4(2);
     - in the General Clauses Act, "1CI", "3CI" and "1I" held s.3(37a)–(59);
     - five more laws had one each.
     - **Readings, all page-read.** Every page's notes block in the GCA is apparatus. A no-cut and set-aside reading
       handles p9's mixed block. A line-wrap reading fixes p5's "(3) of section 94". Openers cover 23 inserted
       definitions that had run on inside their neighbours, among them (8ab) "Federal Government" and (43a)
       "Provincial Government". Neither had its own unit, so neither had a `provision_definition` row; assembly offers
       GCA definitions as defaults to every federal law.
     - **The segmenter variant.** `reviewed_lettered_insertion_subsection` is data-gated and acts only through a
       reading. `reviewed_printed_rule_opener` accepts a lower-case lettered sub-section label (`8ab`, `43ai`,
       `34a1`). It also accepts an opening quote after a sub-section label ("(8) “British possession.”"), a bare note
       marker before "(N)" for sub-sections ("4(20)"), and a starred marker before a lettered insertion ("*5[(43a)").
       No recorded reading could have used these forms (each would have raised), so no other tree changes.
     - **Proof and procedure.** Each law was proved by a tree diff and word conservation. Every lost word was note text
       or an opener's own label and marker, and none was gained except 1992's s.1 heading. Then: a hold, a replay
       with `--approve-release-change`, the verifiers (character recall and precision 1.00000), and the full
       post-replay sequence. All ten golden sets were rebuilt from the live corpus (457 units, 0 problems), because a
       replay re-identifies provisions (D-069). 27 CrPC gold units had pointed at retired rows.
     - **Queued, not repaired:**
       - 6625: its notes use the rules' own "N." style, so more false rules are likely;
       - 3712: the print typesets a note as "15. The words and comma.–";
       - 7416, 8481 and 9315: OCR label misreads;
       - other pages' notes inside the text of 1992, 2840, 3717, 3958 and 4301.

       The detection query: released sections whose label is `^\d{1,2}(CI|Cl|C1)$`, or `^\d{1,2}I$` with an empty or
       "e., …" heading, or whose heading opens "The words" or "Enforced in". ATA s.21I and the like are real.
  5. **Coverage per sub-question** (docs/04 §7; the gate's "coverage of several sub-questions").
     - **Splitting.** `query.sub_questions()` splits a text only when two or more of its sentences end in "?" or "؟".
       The statements before the first question are context every sub-question carries. A sentence ends only before a
       capital, an Urdu letter, a quote or a bracket, so "s. 302" and "Art. 184(3)" never split.
     - **Lexical support, recorded but not judged.** Assembly records, for each sub-question, the admitted units (not
       definitions) that carry at least two of the asked sentence's own content terms (5-letter stems; shared context
       left out). The first build drew a `coverage.partial` verdict from it.
     - **Dev withdrew that verdict.** Of 305 dev cases, 3 ask more than one question, and 2 of them reach assembly.
       Both split correctly, and both were called partial. Both were wrong, because the bundle answers each second
       question in other words:
       - "What does the court look at?" is answered by the minor's welfare;
       - "Do I have to say why I want it?" is answered by "need not give reasons".

       Word overlap cannot see a paraphrase, so `partial` is not emitted. A coverage verdict needs a calibrated judge
       (a cross-encoder per sub-question, with multi-issue gold to fit it on), and both are open.
     - The mechanism is unit-tested, and the dev run checks that no single question splits. It does not change the
       gate, and it retrieves nothing per sub-question.
- Measured on dev (`evals/results/assembly-dev-2026-11-21d.json`: linker /9, the bundles rebuilt from the repaired
  corpus, the D-111 gate). The test split is spent for assembly (D-107, D-108), so it was not re-scored.
  - **GPU, answerable:** necessary units .935 in the bundle, .942 assembled; relevant .370 → .457; text checks .952.
    None lost, 0 INV-5 violations, p50 155 ms, p95 243 ms.
  - **CPU:** necessary units .610 → .620 assembled, i.e. 181 of 292, against 178–179 before D-110; checks .688
    (was .684).
  - **The gate's passing cases:** GPU necessary .966 (249 cases); CPU .951 (99 cases).
  - **Sub-questions:** 2 dev questions split (above). No single question split.
- Where:
  - nizam/retrieval/assembly.py (conflicts, sub_question_coverage), gate.py (GroundingContext.conflicts),
    query.py (sub_questions);
  - nizam/storage/linking.py (lead_in), nizam/workers/links.py (nizam.links/8);
  - nizam/corpus/segment.py (`reviewed_lettered_insertion_subsection`);
  - tools/evidence/footnote-sections-2026-11-21/ (readings, renders), tools/evidence/hold-footnote-sections-2026-11-21.sql;
  - tests/test_assembly*.py, test_linking.py, test_lettered_insertion_subsection.py, test_query_understanding.py;
  - evals/golden/golden-pk-v1-set1..10 (rebuilt); docs/CORPUS-STATE-2026-11-17.md.

### D-109 · 2026-11-21 · Urdu query understanding: Urdu-script places, 26 more concepts, the Roman Urdu frame
Area: owner ruling, L3 query understanding (docs/04 R0) · Status: standing
- Decision: three changes to how an Urdu-language question is read. English questions are unchanged.
  1. **Places** (`nizam/retrieval/places.py`). Urdu-script names of the provinces, territories, capitals and largest
     cities: پنجاب, سندھ, اسلام آباد, آزاد کشمیر, گلگت بلتستان, لاہور, کراچی, پشاور … In a longer name the longer
     match wins: میرپور خاص is Sindh, not AJK's Mirpur. Plain "KP" is added; "KPK" was already there. Before this, an
     Urdu question set no territory, so a Punjab question was searched in every jurisdiction.
  2. **The alias index** (`nizam/retrieval/aliases.py`) gains 26 concepts found missing on dev (general vocabulary,
     not tuned to one question):
     - possession and dispossession (qabza, قبضہ), girl and boy, age words and number words ("solah saal" → sixteen
       years);
     - ECL, grounds, lawful and unlawful, swara/wanni and jirga (PPC s.310A prints "swara" and "wanni");
     - birth, magistrate, deprived, online → electronic information system, dishonour, and fraud in its oblique Urdu
       forms (دھوکے).
     - "zamin" alone is land; "ka/ki/ke zamin" is a surety. They had folded together.
  3. **The Roman Urdu frame.** A Roman Urdu question's function words (hai, mein, ka, ke, ne, kya …) leave its lexical
     query, as English frame words already do. `NIZAM_ROMAN_FRAME=off` is the ablation.
- Measured, CPU hybrid (scoped like D-105), dev:
  - Urdu script (11 cases): r@10 .636 → .773, r@50 .818 → 1.000;
  - Roman Urdu (20 cases): .30 → .35 and .50 → .60;
  - English (245 cases): identical;
  - overall: r@50 .750 → .765, NDCG@10 .445 → .453.
  The frame alone was neutral (identical recall, NDCG +.0003); it is kept because it is cheap and keeps rare words
  from being diluted.
- **Test, once: no gain.**
  - Urdu script (5 cases) was unchanged at .80 / .80.
  - Roman Urdu (14 cases): r@10 .464 → .393, which is one question leaving the top 10; r@50 unchanged at .464.
  - Overall NDCG .397 → .395.

  The dev gain did not carry over to 19 test Urdu questions, and at that size neither direction is distinguishable
  from noise. The places change is right by construction for serving. The harness scopes each question by its gold
  jurisdiction, so it cannot show that change.
- **The gate was not refitted.** The CPU features of the 31 dev and 19 test Urdu questions shift slightly with the
  new lexical queries. The calibration stays gate-v2 until the next refit (open).
- Where: nizam/retrieval/places.py, aliases.py, query.py; tests/test_aliases.py, tests/test_query_understanding.py;
  evals/results/dev-hybrid-d109{-base,-noframe,}-2026-11-21.json, test-hybrid-d109-2026-11-21.json.

### D-108 · 2026-11-21 · The links a provision's words make, as derived tables; assembly reads them
Area: owner ruling, L2 storage (docs/03b §1.1, §10), L3 retrieval (docs/04 §4, §7) · Status: standing
(docs/SCHEMA.md "provision_reference …"; docs/03b, docs/04 as built)
- Decision: the owner asked to "complete retrieval end to end … research intelligently and improve". The first
  dependency was the edges docs/03b names as extractable from text: `defines`, `refers_to`, `subject_to`,
  `notwithstanding`.
  - **Built as derived index tables**, rebuilt from the release under one named rule (`linker`, `nizam.links/7`), as
    `chunk` is (0108), and not as source-keyed evidence. They are a deterministic parse of released text: a replay
    re-derives them, and nothing is decided there that a person must review. Migrations 0114 (provision_reference,
    provision_definition, provision_link_state; legal_edge gains the four kinds) and 0115 (in_heading).
  - **Built by** `nizam/workers/links.py` from the pure rules in `nizam/storage/linking.py`. They are rebuilt whole in
    about 5 minutes, or relinked law by law when a law's versions change or a row points outside the release.
  - **Audit A23** asserts they are exactly the release under one linker, with nothing pointing outside it. Its first
    form, NOT EXISTS against the release views, ran over 30 minutes; set differences take about 100 seconds.
- **The rules** are in docs/SCHEMA.md. Each came from reading samples on dev, through seven linker versions:
  - **Edge kinds.** The phrase is the edge kind; it governs only what it names, and stops at a new clause.
  - **The word printed.** Rules number their own units as rules, so a bare "section 25" in a subordinate instrument
    is its parent Act's.
  - **Other laws.**
    - A reference to another law resolves only when exactly one released law matches the printed title and year.
    - "The Ordinance" means the parent only if the parent is an Ordinance.
    - A run of references shares its trailing law.
    - Footnote markers before a title are tolerated ("the 2Guardian and Wards Act").
  - **Labels.** "Article 23" is never a section; decimal ("12.1"), spaced ("295 C") and hyphenated ("4-A") labels are
    read; "sub-section 4" is not section 4.
  - **Headings.** A schedule's heading "[See section 5]" is read (0115).
  - **Amending laws.** An amending law (Amendment, Adaptation, Repealing, Finance Act) contributes no definitions, and
    its section numbers name the law it amends.
  - **Definition scope.** "In this Act" is the law. "In this Chapter/Part" is that division, for the units printed
    after the definition. A Chapter the tree lacks keeps the definition to its own unit.
  - **Flattened definitions.** A definition stopping at a dash or colon takes its following siblings ("namely:__"
    followed by (i), (ii)); the dashes statutes print are all read.
- **First build** (21 Nov 2026), 10,342 laws:
  - **References:** 166,321. Same law: 67,459 resolved, 22,108 not. Another law: 14,491 resolved, 62,263 not (laws not
    held, OCR damage, amending text).
  - **Definitions:** 72,030 (69,772 whole-law, 462 division, 1,796 unit), 1,977 continued into their siblings.
- **Precision**, read against the text on random samples (author-checked, not a lawyer's review):
  - same-law references: 28/30 on a fresh seed after the third linker, 19/20 on a third seed;
  - cross-law references: 28/30, then 19/20;
  - definition scopes: 25/25.
  Each error found was fixed in the next linker version and is covered by tests/test_linking.py.
- **Graph expansion is not a candidate generator.** On dev, of the necessary gold units the top 50 missed, 1 of 13 on
  the GPU path and 3 of 76 on the CPU path were one link from the top 10. A generator would add 9–27 neighbours per
  question to the reranker slate for at most that. So docs/04 §4's graph and definition generators are the
  completeness pass of assembly (docs/04 §7), which now reads the tables:
  - qualifications and references, in printed order, into the same law and into others;
  - **provisions that say "notwithstanding" a bundle unit**, which prevail over it (up to 3);
  - definitions from the law, then the parent Act (empowers), then the jurisdiction's own General Clauses Act
    (`defaults_from`, at most 3 per unit). The Act is federal 1897 or the Punjab/KP 1956 copies; Sindh, Balochistan,
    AJK and GB hold none, and none is guessed.
  - Drafting words ("section", "year") and too-general words ("person", place names) are never attached from a
    General Clauses Act.
- **Assembly measured.** The rule is D-107's; the budget is unchanged at 50,000 characters.

  | | necessary | relevant | text checks | p50 / p95 |
  |---|---|---|---|---|
  | dev, GPU bundles | 275/292 (=) | 21/46 (=) | 238/250 (=) | 233/398 → 145/236 ms |
  | dev, CPU bundles | 178 → 179/292 | 10 → 9/46 | 171/250 → 172/250 | p95 1,472 → 893 ms |
  | test (once), GPU | 169/182 (=) | 17/27 (=) | 147 → 146/155 | 227/376 → 154/248 ms |
  | test (once), CPU | 103/182 (=) | 8/27 (=) | 95/155 (=) | p95 725 → 783 ms |

  - No necessary unit the bundle held was lost; 0 INV-5 violations in either split.
  - **The lost test text check** (S9-U05) and the dev relevant unit (S5-C02) are budget trade-offs. The packet filled
    (49,947 characters, 25 items skipped) and a bundle unit holding the text was crowded out by earlier units' new
    additions.
  - A dev attempt to defer each unit's definitions past every unit's references cost two necessary units and was
    reverted.
  - **New kinds of addition, read on dev** (10 per kind):
    - cross-law references 10/10;
    - prevailing provisions 8/10, one fixed in linker 7, one unreadable OCR;
    - parent-law definitions 9/10, fixed in linker 7;
    - General Clauses Act definitions 10/10.
  - **All additions on test** (final version, once): 39/40. The error was a "company" definition of s.404 of the
    Punjab Labour Code reaching s.165; the section's own scope words are in a sibling Explanation the rule does not
    read.
- **Latency.** The view by version ids is 47 ms of the ~150 ms, and the delegation records and the General Clauses
  Acts are now read once per process. The rest is row fetching. The subtree closure (provision_ancestor), LATERAL
  and ltree forms all took 14–18 ms for a 605-row bundle on this laptop.
- Where:
  - infra/postgres/migrations/0114_provision_links.sql, 0115_provision_reference_in_heading.sql;
  - nizam/storage/linking.py, nizam/workers/links.py, nizam/storage/evidence_read.py, nizam/retrieval/assembly.py;
  - tools/audit/criteria.sql (A23);
  - tests/test_linking.py, tests/test_links_db.py, tests/test_assembly*.py;
  - evals/results/assembly-{dev,test}-2026-11-21.json;
  - evals/golden/review/assembly-additions-test-2026-11-21.json, assembly-new-kinds-dev-2026-11-21.json;
  - docs/SCHEMA.md, docs/03b, docs/04 §4.

### D-107 · 2026-11-20 · Evidence assembly: whole units, with their definitions, qualifications and references
Area: owner ruling, L3 retrieval (docs/04 §7), L2 reads · Status: standing (docs/04 §7 as built)
- Decision: the owner asked for context assembly "completely end to end", tested for accuracy.
  `nizam/retrieval/assembly.py: assemble()` runs inside `retrieve()` after the gate passes and changes nothing the
  gate decided:
  - `GroundingContext.items` keeps the bundle the gate judged (INV-3). Its type is renamed `BundleItem`: docs/04
    §7's `EvidenceItem` is the assembled item.
  - `GroundingContext.evidence` holds the assembled items, in the law's own order.
  - `GroundingContext.coverage` records what was skipped and why, with step timings and what is not built.
  - If no bundle unit is law at `as_of` any more (the corpus changed between the two reads), `retrieve()` abstains
    (`INSUFFICIENT_EVIDENCE`, stage `assembly`). INV-2 holds: still exactly two values.
- **The reads** (`nizam/storage/evidence_read.py`, L2). Text and law facts come only from `operative_provision`,
  asked by version ids. Structure (ids, paths, labels, pages, order) comes from the base tables, as a pre-filter that
  never decides what is law.
  - The view by ids took 7 ms under a generic plan and 35 ms under a custom one. Per-unit `LATERAL` reads of the
    view took 20 s (the join trap). So the evidence session plans generically. It reads no `pg_search` index, so
    D-097's custom-plan rule does not apply.
  - Amendment footnotes come from `v_amendment_reference_current`, filtered by the laws' source observations, which
    the view's `DISTINCT ON` takes inside it (170 → 60 ms).
- **The rules** (docs/04 §7: governing rule first, then what it needs, then corroboration). Each item records its
  inclusion reason:
  1. Every bundle unit is admitted **whole**: every operative sub-section, clause, proviso, explanation and
     illustration, in printed order. Never half a section.
  2. **A Part or Chapter in the bundle is replaced by its sections.** Retrieval maps a match on its heading to the
     division itself; 56 dev cases had one. A division is not a citable unit (INV-4), and whole it swallowed the
     bundle's own sections: it lost 6 necessary units on dev. The replacement takes sections not already in the
     bundle, in printed order: at most 5, within a quarter of the budget, skipping '[Omitted]' stubs.
  3. **Qualifications:** up to 3 units of the same law the unit is "subject to", "notwithstanding", "save as / except
     as provided in" or "without prejudice to".
  4. **Definitions:** up to 8 per unit, by first use. A definition is a clause of the same law that defines a word
     the unit uses (means, includes, denotes, signifies, has the meaning). One definition is kept per word: the
     narrowest scope that reaches the unit.
     - **Scope comes from the opening words:**
       - "In this Act" reaches the whole law, so Art. 260 reaches back.
       - "In this Chapter/Part" reaches the units of that division printed after the definition.
       - "In this section" stays inside the unit.
       - A named Chapter the tree lacks reaches no further than the definition's own unit.
     - **Words that name an instrument** ("Act", "Code", "Rules") count only as "the/this/said Act", never as the
       last word of another law's title.
     - **An amending or Finance law contributes no definitions.**
     - **A definition that stops mid-sentence** ("means--", "namely:__") with no sub-clauses takes its following
       siblings until the next definition (at most 15 nodes, 3,000 characters). The segmenter often flattens sub-items
       into siblings. A definition still empty after that is dropped and recorded.
  5. **References and schedules:** up to 3 more units or schedules of the same law that the unit names. A reference
     to another law is counted but not followed. Such a reference is one followed by "of the X Act", or with a law
     title earlier in the same sentence, or any reference in an amending law.
  6. **What each item carries:**
     - a citation in the server's form (`library_read.render_citation`, D-070: "…, s. 2(1)(e)", "…, Art. 25" for a
       constitution's sections);
     - its Part and Chapter, and the law's facts at `as_of` in the territory;
     - up to 12 printed amendment footnotes, and up to 5 instruments made under it (`empowers`, 0089);
     - its source URL, file sha256 and pages.
  7. **The budget selector** admits in that priority order. It skips an item that does not fit (it never cuts one)
     and never repeats what an admitted unit already holds. A whole unit replaces a clause of it admitted earlier.
     The first governing unit is always admitted, and if it alone exceeds the budget that is recorded. At most 20
     whole units are admitted (docs/04 §7); definitions are bounded by the per-unit cap and the budget.
- **Budget: 50,000 characters** (about 12.5k tokens). docs/05 §5.2 sets no figure. The rule
  (`evals/results/assembly-rule-2026-11-20.json`, written before any metric) took the smallest multiple of 5,000 at
  or above the dev p90 of the unconstrained GPU packet, 48,593 characters.
- **Measured** (provisional: golden sets are drafts). The arms are `passages` (what the reranker read), `units` (the
  bundle whole) and `assembled`; answerable questions; GPU bundles; test assembled once on the frozen version (sha256
  7d0a42c5…):

  | | dev 276: necessary / relevant / text checks | test 174: necessary / relevant / text checks |
  |---|---|---|
  | passages | 273/292 · 17/46 · 236/250 | 166/182 · 15/27 · 147/155 |
  | bundle whole | 273/292 · 17/46 · 237/250 | 166/182 · 15/27 · 147/155 |
  | **assembled** | **275/292 · 21/46 · 238/250** | **169/182 · 17/27 · 147/155** |

  - **No necessary unit the bundle held was lost** in either split or mode. On the CPU bundles: dev necessary 174 →
    178, test 100 → 103.
  - **INV-5:** every node of every packet was re-asked of `operative_provision` independently: 0 violations.
  - **Additions read against the law** (M4, 40 by a fixed seed; author-checked, not a lawyer's review):
    - dev round 1: 37/40; round 2, after the first fixes: 38/40; round 3, the final version: 40/40;
    - **test, once, on the frozen version: 38/40.** Both test errors were flattened definitions (Copyright Ordinance
      s.2(m), s.2(zf)). The continuation rule above was added after test for exactly that, and was measured on dev
      only.
  - **Size:** p50 20k and p90 42k characters per GPU packet; about 13 units and 11 definitions. The CPU bundles run
    larger, and 4 dev packets exceed the budget on their first unit alone.
  - **Latency:** assembly p50 about 230 ms and p95 about 400 ms (GPU bundles); CPU p95 0.7–1.5 s. docs/04 §9's
    "validate / assemble / gate ≤ 25 ms" is not met (open).
- Why: docs/04 §7, "retrieve narrow; assemble complete". A clause alone can mislead: the proviso, the definition of
  "employer", or the section "subject to" which it applies sit outside the match.
- Where:
  - nizam/retrieval/assembly.py; nizam/storage/evidence_read.py;
  - nizam/retrieval/gate.py (`BundleItem`, `GroundingContext.evidence` and `coverage`, `retrieve(assemble=)`);
  - tests/test_assembly.py, tests/test_assembly_db.py;
  - evals/assembly_eval.py; evals/results/assembly-rule-2026-11-20.json, assembly-dev-sizes-2026-11-20.json,
    assembly-{dev,test}-2026-11-20.json; evals/golden/review/assembly-additions-dev-2026-11-20-r{1,2,3}.json and
    assembly-additions-test-2026-11-20.json;
  - docs/04 §7.

### D-106 · 2026-11-20 · Gate v2: three more scope vetoes, a refit on the 500-case split, and the degraded mode gated
Area: owner ruling, L3 retrieval (docs/04 §8, §9.2), evaluation · Status: standing (supersedes D-102's calibration
and its "unreranked abstains" outcome; D-102's decision order is unchanged)
- Decision: the last of the owner's "do all … end to end" improvements to D-102's gate. A second addendum to the gate
  rule (`evals/results/gate-rule-addendum-scope-2026-11-20.json`) was written before the 500-case features existed
  and before any refit. It adds three vetoes and fixes the refit; nothing else in the rule changes.
  - **Three scope vetoes** (`nizam/retrieval/scope.py`), after time, source and place, all → `CORPUS_GAP` with their
    own public reason. Each is tied to a legal noun or a counted noun, never to a mention (D-102):
    - **records:** a particular person's, property's or company's record ("is there an FIR against my CNIC", "is my
      name on the ECL", "does <Name> hold a licence"). Records are not in the library.
    - **statistics:** "how many" + a counted noun (cases, FIRs, complaints, marriages…) + a filing verb (registered,
      filed, reported, decided). "How many days do I have to appeal?" passes.
    - **live:** a live figure (an exchange, policy or market rate or price; gold, petrol, the air quality index;
      what something is worth) with today, now, current or latest. "What is the current minimum wage?" asks the law
      in force and passes.
  - **The refit.** Features were recomputed for all 500 cases (D-104) in all three modes. That run used the corpus
    after D-103 and the alias index (D-105). The 8B GPU path now covers every case: 15,971 pairs were scored on
    Kaggle (`rrg2-8b`, all finite; only questions and passages left the laptop). The same selection was used (F1–F5,
    leave-one-family-out log loss on dev 305) with the same threshold rule. `gate_calibration.json` is now
    `gate-v2-2026-11-20`.
- Dev, out of fold (`evals/results/gate-fit-dev-2026-11-20.json`):

  | mode | features | log loss | τ | target | passed / 305 | answered precision | coverage of sufficient |
  |---|---|---|---|---|---|---|---|
  | **gpu** (Qwen3-Reranker-8B) | top | .232 | .671 | .95 | 262 | .950 | .954 (261) |
  | **cpu** (int8 mMiniLM) | top, margin, agree | .506 | .761 | .95 | 100 | .950 | .549 (173) |
  | **unreranked** (fused order) | top, margin | .587 | .798 | **.90** (fallback) | 20 | .900 | .104 (173) |

  On 120 dev cases (D-102), unreranked plateaued near .77. On 305 it reaches the 0.90 fallback at 10.4% coverage,
  just above the rule's 10% floor. So the degraded mode now answers its clearest questions, under its own threshold
  (docs/04 §9.2), instead of always abstaining.
- **Test, scored once** after the calibration was frozen (`evals/results/gate-test-2026-11-20.json`, 195 cases: 174
  answerable, 21 unanswerable). Provisional: golden sets are drafts, κ not measured.

  | test 195 | passed | answered precision (Wilson 95%) | coverage of sufficient | of answerable | unanswerable abstained (L3 scope) | ECE |
  |---|---|---|---|---|---|---|
  | **gpu** | 166 | **.940** [.893, .967] | .957 | .948 | 20 / 21 (19 / 19) | .044 |
  | **cpu** | 55 | **.909** [.804, .961] | .505 | .316 | 21 / 21 (19 / 19) | .067 |
  | **unreranked** | 18 | **1.0** [.824, 1.0] | .182 | .103 | 21 / 21 (19 / 19) | .094 |

  On D-102's own 80 test cases, for comparison (reporting only):

  | mode | D-102 | gate v2 |
  |---|---|---|
  | gpu | 72 at .944 | 71 at .958 |
  | cpu | 18 at .833 | **29 at .862** |
  | unreranked | 0 | **10 at 1.0** |

  - **GPU wrong answers (10).** Each is a passed bundle that lacks a necessary unit (S2-C06, S4-C05, S6-C17, S6-R01,
    S7-C10, S8-C03, S8-R04, S8-U04, S9-R06), plus S4-X05, a guarantee request that is L6's professional-review case.
    S3-X04, D-102's statistics miss, is now vetoed. The GPU's only unanswerable miss is S4-X05.
  - **The CPU gate is still under 0.95 on test,** but its interval now contains the target. On the same 80 cases it
    answers 29 where D-102 answered 18. Urdu on the CPU still passes almost nothing (Roman Urdu 1 of 14).
  - **Vetoes fired on no answerable case** in dev or test. On test they abstained 13 times with the right code: time
    3, source 4, place 2, records 2, statistics 2.
  - **Authorship caveat.** The lead wrote both the golden cases (test included) and the veto patterns, so the veto
    rows are optimistic. The honest measure is the classifier alone: on test it caught 17 of 21 unanswerable
    questions on the GPU and 20 of 21 on the CPU.
  - **docs/10's abstention targets** (precision ≥ .90 and recall ≥ .85 on the unanswerable stratum):
    - recall is met on test in every mode (GPU .952);
    - strict abstention precision is not (GPU .690, because 7 of 29 GPU abstentions are on answerable questions whose
      bundle was sufficient).
- **8B reranker latency, a proxy** (slice 7; `rrg2-8b` `latency-qwen3-8b.json`; Kaggle T4, fp16, one question's
  passages micro-batched at 16,384 tokens, 20 questions):

  | passages | p50 | p95 |
  |---|---|---|
  | 10 | 4.5 s | 8.5 s |
  | 50 | 24.5 s | 30.6 s |

  On a T4 the 8B reranker is far outside docs/10's 1.5 s p50, so it is not serveable as measured. A T4 is not the
  serving host. Whether an L4/A10-class GPU with TEI or vLLM batching meets the budget stays open.
- Housekeeping:
  - D-102's gate result files moved to `evals/results/prior/*-d102.json`. The current names hold v2.
  - The fitted files' "provisional" label wrongly read "golden sets 1-4". It was corrected in `gate_fit.py`,
    `gate_features.py` and `gate_eval.py`, and fit and eval were re-run: the numbers are identical. The calibration's
    sha256 is 689639a6….
  - `gate_features`' MultiReranker reads a grown pairs file only up to each score file's length.
- Why: D-102's CPU gate fell from .952 out-of-fold on 120 dev cases to .833 on test. Its recorded remedy was more dev
  cases, never test-driven tuning, and D-104 supplied them. D-102's error analysis also found question kinds no
  statute answers (live figures, record lookups, statistics), which only a scope rule can refuse honestly.
- Where:
  - nizam/retrieval/scope.py (records_veto, statistics_veto, live_veto, veto order);
  - nizam/retrieval/gate.py (PUBLIC reasons for CORPUS_GAP:records, :statistics, :live);
  - nizam/retrieval/gate_calibration.json;
  - evals/{gate_features.py, gate_fit.py, gate_eval.py};
  - evals/results/gate-rule-addendum-scope-2026-11-20.json, gate-features-{dev,test}-2026-11-20.json,
    gate-fit-dev-2026-11-20.json, gate-{dev,test}-2026-11-20.json, prior/;
  - tests/test_scope.py; docs/04 §8, §9.2.

### D-105 · 2026-11-20 · The legal alias index: Urdu and Roman Urdu questions gain English legal words
Area: owner ruling, L3 query understanding (docs/04 R0) · Status: standing
- Decision: `nizam/retrieval/aliases.py` maps about 150 legal concepts to the English words the statute book uses.
  They cover family, property, criminal, labour, money, procedure and public law, in Roman Urdu spellings and Urdu
  script. `query.parse` adds those words to the lexical (BM25) query of a question written in Urdu: Urdu script, or
  Roman Urdu recognised by at least two of its function words (hai, mein, kya, ka, ki, ke…).
  - **An English question is never changed;** no dev English question was.
  - **The question's own words stay.** Only an Urdu-script question, which the English index cannot read at all, is
    searched by its gloss alone.
  - **Spelling variants meet:** k/q, doubled letters, aa/ee/oo, a trailing h. Phrases match before their parts
    ("haq mehr", "makan malik"). Urdu script is matched word by word, with diacritics, the zero-width non-joiner and
    Urdu punctuation removed.
  - **Dense search and the reranker still read the question as written.** The GPU path's 8B vectors are keyed by
    exact text, and its slate has no BM25 windows, so the GPU path is unchanged.
  - `NIZAM_ALIASES=off` is the ablation arm.
- Why: docs/04 R0, "Roman Urdu is first-class". On the CPU path, Roman Urdu questions found the needed law in the
  top 50 for only 10% of dev cases: no CPU generator read them (D-101).
- Measured on the CPU hybrid. The vocabulary is general; dev questions showed gaps (loanwords in Urdu script,
  pabandi, zimmedar, izzat…) that were filled with general terms. The test split was run once, after:

  | | dev 276 r@10 / r@50 / NDCG@10 | test 174 (once) r@10 / r@50 / NDCG@10 |
  |---|---|---|
  | aliases off | .592 / .714 / .434 | .526 / .687 / .377 |
  | **aliases on** | **.611 / .750 / .445** | **.558 / .707 / .397** |
  | Roman Urdu | .10 / .10 → .30 / .50 (20) | .21 / .29 → .46 / .46 (14) |
  | Urdu script | .55 / .64 → .64 / .82 (11) | .40 / .60 → .80 / .80 (5) |

  English rows are identical with and without. Latency is unchanged (dev p50 914 → 842 ms).
- Not done: docs/04's 400–600 concepts (the table has about 150); Urdu-script place names for territory detection; a
  paired bootstrap (the Urdu strata are 20 and 14 cases).
- Where: nizam/retrieval/aliases.py, nizam/retrieval/query.py (QuerySpec.gloss); tests/test_aliases.py;
  evals/results/{dev,test}-hybrid-aliases-{off,on}-2026-11-20.json.

### D-104 · 2026-11-20 · Golden sets 5–10: the 500-case set is complete in draft
Area: owner ruling, evaluation (docs/10 §4) · Status: standing (evals/golden/README.md)
- Decision: the owner asked for every improvement to D-102's gate, end to end. The first is more cases. The D-102 CPU
  gate was fitted on 120 dev cases (12 unanswerable), and its out-of-fold .952 fell to .833 on test. Six new sets of
  50 bring the golden set to its 500-case target:

  | set | area |
  |---|---|
  | 5 | property and land |
  | 6 | criminal law and procedure II |
  | 7 | family and personal status II |
  | 8 | public law |
  | 9 | commerce, money and private lending |
  | 10 | welfare and regulation by place, and Gilgit-Baltistan |

  - **Built the same way as sets 1–4.** Cases were authored from the law's own text read with `peek.py`, never from
    system output (stage A0). Every provision is resolved and checked served on the case's date in its territory
    (A3). Every answer case has `check` phrases found in its necessary text. Each set keeps the strata mix: 20
    citizen, 12 professional, 8 procedural, 5 Urdu/Roman Urdu, 5 unanswerable. Families stay inside their set and do
    not reuse sets 1–4's topics.
  - **New traps.** Each case names the law a system must not serve for it, where there is one:
    - the ICT women's-property Act for a Punjab question;
    - the federal narcotics Act in Sindh (repealed there by Sindh's own 2024 Act);
    - each province's private-loan interest ban for the others;
    - the federal environmental penalty in KP (repealed there, D-103).
  - **New unanswerable kinds,** from D-102's error analysis: market and live figures, register lookups, a false
    premise (an Act that does not exist), outcome predictions, future budgets, and foreign law in several forms.
  - **Built clean.** All ten sets report problems 0, and none fails an existing check. Set 3 keeps its two known
    observations: the Punjab texts of the Child Marriage Restraint Act 1929 and the Defamation Ordinance 2002 are
    correctly refused before their capture.
  - **Split** (`evals/golden/split.py`, D-098's rule, unchanged; no existing case moved):
    - dev 305 cases (254 answer, 22 conditional, 29 unanswerable);
    - test 195 (161, 13, 21).
- Deliberately left out of the new sets, each recorded in its builder's docstring:
  - articles changed by the 26th and 27th Amendments' court provisions;
  - the Transgender Persons Act (parts declared repugnant by the Federal Shariat Court; appeal status unverified);
  - the Christian marriage ages and the Divorce Act 1869 (their amendment status is unverified);
  - Sindh's disability Act (mis-segmented);
  - GB pre-emption after s.6 (labels shifted);
  - Punjab labour law (below).
- Still draft: stages A1 and A2 (two legal annotators, κ, a senior advocate) are not done. Every figure measured on
  these sets stays provisional (D-095).
- Where: evals/golden/build_set{5..10}.py, golden-pk-v1-set{5..10}.draft.{jsonl,md}, split-v1.json, README.md;
  evals/golden/review/gate-error-notes-2026-11-20.md (two cases where the draft gold may be narrower than the law).

### D-103 · 2026-11-20 · Repeal recorders read plurals and own-province wordings: 32 missed repeals recorded
Area: L1/L2 corpus rule (repeals, INV-5) · Status: standing (docs/SCHEMA.md "Where a law runs")
- Found by the gate's error analysis (D-102). Test case S4-C05 asks about maternity pay in Peshawar. The system
  served the West Pakistan Maternity Benefit Ordinance, 1958, which the KP Maternity Benefits Act, 2013 s.18
  repeals "in its application to the province of the Khyber Pakhtunkhwa". 62 of the Ordinance's provisions were
  operative in KP. That is repealed law served as in force, the failure INV-5 exists to prevent. Two misses
  compounded:
  - the clause names "Maternity Benefit**s** Ordinance" (the held title is singular);
  - the KP place pattern did not take "the province **of the** Khyber Pakhtunkhwa" (Punjab's did).
- Decision. Both recorders keep their rules and gain three narrow readings, each tested
  (tests/test_territorial_repeal_clause.py, tests/test_statutory_repeal.py):
  1. **Plural fallback.** When the exact title and year find no law, a title equal but for plural endings
     (`fold_plural`) may match, still requiring a single law (or twins) and recording "title equal but for a
     plural".
  2. **Own-province wordings** (territorial):
     - "the province of the …" for every province;
     - "Balochistan Province";
     - "its applicability to …";
     - footnote brackets ("the 2[Khyber Pakhtunkhwa]");
     - a provincial Act's "the province" / "this province" for itself.
     Also fixed: the `||` the clause reader joins its two halves with was left on the place.
  3. **A qualifier naming only the repealer's own province** (statutory). It repeals the whole of that province's
     own copy (the Balochistan copy of the 1958 Ordinance); any other qualifier is still skipped.
- Recorded, every clause read before applying:
  - **23 territorial repeals.** Among them: the Pakistan Environmental Protection Act 1997, Payment of Wages Act
    1936, Mental Health Ordinance 2001, Employment of Children Act 1991 (KP and Sindh), Explosive Substances Act
    1908 and Zakat and Ushr Ordinance 1980 in KP; the Maternity Benefit Ordinance 1958 in KP and Balochistan; the
    Probation of Offenders Ordinance 1960 in Balochistan; the Glanders and Farcy Act 1899 in Punjab.
  - **9 statutory repeals.** Among them: the Punjab Agricultural Produce Markets Ordinance 1978, the Sind Drug
    Advertisement Control Act 1948, and Balochistan's and KP's own copies of two pre-1970 laws.
  - Then `apply_statutory_repeals`, `refresh_serving`, and the audit: **44 of 44 pass**. Current laws went from
    8,246 to 8,242. The 1958 Ordinance's provisions operative in KP went from 62 to 0.
- Still unread, reported by the recorder: 16 qualifiers name places it does not read (Turbat University campuses,
  Karachi lists, "the tribal areas of the province of Balochistan"). Each needs a page read, not a rule.
- The gate's features (D-102) were measured before this fix; the next refit measures the corrected corpus.
- Where: tools/record_territorial_repeals.py (PLACE, OWN_PROVINCE, LEAD, place_of, the plural fallback);
  tools/record_statutory_repeals.py (fold_plural, the own-province copy rule); tests above;
  docs/CORPUS-STATE-2026-11-17.md; CLAUDE.md.

### D-102 · 2026-11-20 · The sufficiency gate: vetoes, a calibrated classifier per reranker, and retrieve()
Area: owner ruling, L3 retrieval, evaluation · Status: standing (docs/04 §8, §9.2, as built)
- Decision: the owner asked to "build the gate end to end fully and improve it and test it". L3 now has its port,
  `nizam.retrieval.gate.retrieve(question, Filters) -> GroundingContext | Abstention`. It has exactly two values
  (INV-2): no retry at a lower threshold, no fallback, no low-confidence third result. It decides in this order,
  and each step is recorded in the result's `gate` dict with the retrieval trace (INV-3):
  1. **Scope vetoes, before any search** (`nizam/retrieval/scope.py`, docs/04 §8 "time / place / source"). Pure
     rules over the question:
     - time: `as_of` after today, or a question about what the law *will be* ("What will the slabs be in 2029?")
       → `NO_VALID_VERSION`;
     - source: what a court, tribunal or ombudsman decided, case law, or a law-report citation → `CORPUS_GAP` (no
       judgments yet, D-100);
     - place: a body of law of a foreign place ("labour laws in Saudi Arabia", "Indian law", "UAE visa") with no
       Pakistani place in the question → `CORPUS_GAP`.
     A mention is not a veto. Facts abroad ("my husband lives in Saudi Arabia"), procedure ("appeal the judgment of
     the civil court") and future facts ("rent due next month") pass. Latin script only for now.
  2. **The served retrieval** (`ranked()`, D-101). Nothing found → `INSUFFICIENT_EVIDENCE`.
  3. **Territory veto** (docs/04 §10.3). No territory given or found while the bundle's first 5 units hold
     provincial laws of two or more provinces → `JURISDICTION_UNRESOLVED`, asking for the province
     (`unit_search.Session.instrument_jurisdictions`).
  4. **The calibration of the mode that actually ran.** Reranked modes are matched by the reranker's model and
     revision; unreranked is matched by its slate's dense space. A mode with none → `RETRIEVAL_DEGRADED`
     (docs/04 §9.2). No mode borrows another's threshold.
  5. **p = sigmoid(w·z + b) over the bundle's features; pass iff p ≥ τ.** Below τ → `INSUFFICIENT_EVIDENCE`, with the
     5 nearest units attached as `nearest`, never as evidence. Every abstention carries a public reason and an
     actionable suggestion (docs/04 §8.1).
  A `GroundingContext` holds identities and scores of the first 10 units (the bundle). Assembly into whole provisions
  with definitions (docs/04 §7) is the next component.
- How it was fitted: by a rule written before any gate score existed (`evals/results/gate-rule-2026-11-20.json`).
  - **Label.** "Sufficient" means the case expects an answer and every proposition's necessary unit is in the first
    10 served units. Abstain cases are always insufficient.
  - **Model.** Logistic regression in numpy (standardised, L2 λ = 1). Serving needs no library and no model file:
    `nizam/retrieval/gate_calibration.json` is data.
  - **Selection.** Leave-one-family-out cross-validation on dev (120 cases), lowest out-of-fold log loss.
  - **Threshold.** τ is the smallest out-of-fold probability giving answered precision ≥ 0.95 with ≥ 5 passing
    (fallback 0.90 below 10% coverage; none below that).
  - **Inputs.** `evals/gate_features.py` runs the served path for answerable and abstain cases alike. The GPU mode
    replays 8B question vectors and Qwen3-Reranker-8B scores from Kaggle. The 20 abstain questions were encoded
    (q8x1: dev re-encode cosine 1.0) and their 974 pairs scored (rrg-8b: complete, then OOM in the latency step as in
    D-101); only questions and passages left the laptop.
  - **One addendum, on dev, before its feature existed** (`gate-rule-addendum-agree-2026-11-20.json`). The first fit
    passed 7 of 120 dev cases on the CPU, and the rule had omitted docs/04 §8.1's "generator agreement". The addendum
    added `agree`: how many generators (lexical, dense, citation) rank the lead unit in their first 10. Test had not
    been scored in any mode.

  | dev, out-of-fold | chosen features | log loss | τ | passed | answered precision | coverage of sufficient |
  |---|---|---|---|---|---|---|
  | **gpu** (Qwen3-Reranker-8B, citations + 8B dense) | top | .225 | .730 | 106 / 120 | .953 | .953 (106) |
  | **cpu** (int8 mMiniLM, hybrid) | top, margin, agree (F2 alone: .543) | .506 | .895 | 21 / 120 | .952 | .290 (69) |
  | **unreranked** (hybrid, fused order) | best F3, .616 | — | none | — | plateaus near .77 | ships no calibration |

- Test, scored once after the calibration was frozen (sha256 32d5bbc4…; provisional, golden sets are drafts, κ not
  measured; `evals/gate_eval.py`):

  | test (80: 72 answerable, 8 unanswerable) | passed | answered precision (Wilson 95%) | coverage of sufficient | of answerable | unanswerable abstained | ECE |
  |---|---|---|---|---|---|---|
  | **gpu** | 72 | **.944** [.866, .978] | .986 | .972 | 6 / 8 (L3-scope 5 / 6) | .022 |
  | **cpu** | 18 | **.833** [.608, .942] | .375 | .236 | 7 / 8 (5 / 6) | .104 |
  | **unreranked** | 0 | — | 0 | 0 | 8 / 8 | — |

  - **GPU wrong answers (4).** Two answerable cases whose bundle lacks the gold unit (S2-C06, S4-C05). A question
    about how many cases a law has had (S3-X04). One about a penalty guarantee (S4-X05, an L6 professional-review
    case, below).
  - Urdu and Roman Urdu on the GPU: 8 of 8 pass, all sufficient. The CPU passes none (no CPU generator reads Roman
    Urdu, D-101).
  - **The CPU gate is below its target on test.** At n = 18 its interval excludes 0.95. Dev's out-of-fold .952 was
    optimistic. Nothing was changed after seeing test; see the open question.
  - **docs/10's abstention targets (precision ≥ .90, recall ≥ .85 on the unanswerable stratum) are not met.**
    - GPU: strict precision .75, recall .75.
    - CPU: recall .875, but strict precision .11, because it declines most answerable questions.
    - Eight unanswerable test cases cannot carry those figures; the stratum needs the remaining golden sets.
  - **Vetoes.** None fired on any answerable case in either split. On test they matched the classifier's recall and
    added the right reason code (place, time, source). The test unanswerable questions were listed once before the
    veto rules were written (counting the split), so the veto rows are optimistic; the classifier rows are not.
- Not the gate's: questions asking for a predicted outcome or a recommendation (golden code
  `professional_review_required`) are L6's outcome (docs/07). They are reported in their own row and chose nothing.
- Why: INV-2 needs a gate whose threshold is fitted, not chosen, and docs/04 §9.2 needs the degraded mode gated
  separately. On the GPU profile the gate holds back almost nothing answerable (97% of answerable test questions
  pass) while keeping precision near the target. The unreranked mode keeps abstaining because no threshold earned
  the target.
- Where:
  - nizam/retrieval/gate.py (retrieve, gate, features, mode_of, probability, territory_veto; EvidenceItem,
    GroundingContext, Abstention); nizam/retrieval/scope.py; nizam/retrieval/gate_calibration.json;
    nizam/storage/unit_search.py (instrument_jurisdictions);
  - evals/{gate_features.py, gate_fit.py, gate_eval.py};
  - evals/results/gate-rule-2026-11-20.json, gate-rule-addendum-agree-2026-11-20.json,
    gate-features-{dev,test}-2026-11-20.json, gate-fit-dev-2026-11-20.json, gate-{dev,test}-2026-11-20.json;
  - tests/{test_gate.py, test_scope.py, test_gate_db.py};
  - docs/04 §8 and §9.2 (as built).

### D-101 · 2026-11-20 · The cross-encoder: Qwen3-Reranker-8B on the GPU host, int8 mMiniLM on the CPU
Area: owner ruling, L3 retrieval, inference, evaluation · Status: standing (docs/04 §5.1, §9, as built)
- Decision: the owner asked for "reranker end to end fully and test it". L3's candidates are now reranked
  (`nizam/retrieval/rerank.py: ranked()`), one model per dense profile:

  | profile | reranker | slate | reads | where it runs |
  |---|---|---|---|---|
  | **gpu** | Qwen/Qwen3-Reranker-8B @ 77d193c7 (yes/no logit, the bake-off's instruction) | citations, then 8B dense (no BM25 windows) | 1,600 characters × 50 units | a service on the GPU host (`NIZAM_GPU_RERANKER_URL`, TEI or vLLM), refused unless it ranks 6 reference groups as the bake-off did (Spearman ≥ 0.98) |
  | **cpu** | cross-encoder/mmarco-mMiniLMv2-L12-H384-v1 @ 1427fd65, int8 ONNX, per-channel | the hybrid (citations, then RRF of lexical and bge-m3) | 800 characters × 10 units; deeper units keep the fused order | in process (`nizam.inference.reranker.OnnxReranker`, `models/reranker`) |

  - **Cited units stay first, in their order.** A section the user named is their own identifier (docs/04 §2.2).
    The reranker orders the rest, and ties keep the fused order.
  - **The passage is read through `operative_provision`** at the request's `as_of` and territory
    (`unit_search.Session.unit_passages`). It is the unit's chunk context prefix, then its operative nodes in
    printed order, so a repealed or uncommenced sub-section never reaches the model (INV-5).
  - **Every unit's score goes in the trace (INV-3),** with the model, revision, device, passage length, depth and
    stage times. `UnitCandidate.rerank_score` carries it. No chunk id leaves L3 (INV-4).
  - **Degradation is marked (docs/04 §9.2).** A GPU reranker that cannot load or answer falls back to the CPU one,
    marked `rerank_cpu`. No reranker, `NIZAM_RERANK_PROFILE=off`, or a mid-request failure (OSError or ValueError)
    serves the fused order marked `unreranked`. Any other error is an error.
  - **The GPU slate settles D-099's fusion question for that profile.** With the 8B space, lexical keeps only the
    citation fast path ahead of dense; BM25 windows are not in its slate. The reranker scores 8B's citations-then-
    dense slate higher than the hybrid one (dev .832 against .824 NDCG@10), and the unreranked dense-led slate is
    better too (.704 against .573).
- How it was chosen: by a rule written before any reranker score existed (`evals/results/rerank-rule-2026-11-20.json`;
  owner priority, accuracy first).
  1. **Bake-off on dev** (108 answerable cases). Six models, both slates, both profiles: 11,346 pairs scored on
     Kaggle T4s in fp16 (`tools/kaggle/rerank_kernel.py`). Only questions and passages left the laptop; the gold
     stayed in `slates.json`. Scored by `evals/rerank_eval.py` (binary NDCG@10, each gold unit credited once, MRR@10).
     jina-reranker-v2 was excluded (CC-BY-NC-4.0).

     | dev NDCG@10 / MRR@10 | unreranked | mMiniLM | gte-ml | bge-v2-m3 | Qwen3-0.6B | Qwen3-4B | Qwen3-8B |
     |---|---|---|---|---|---|---|---|
     | gpu / citations + dense | .704 / .659 | worse than unreranked (small models) | | | | .782 / .739 | **.832 / .802** |
     | gpu / hybrid | .573 / .524 | | | | | | .824 / .797 |
     | cpu / hybrid | .454 / .412 | .496 / .450 | .546 / .499 | **.601 / .567** | .567 / .527 | (not allowed) | |
     | cpu / citations + dense | .469 / .433 | .501 / .452 | .567 / .518 | .600 / .562 | .564 / .523 | | |

     - GPU: 8B on citations + dense, +25.9 NDCG@10 [18.7, 33.0] over the unreranked hybrid (56 better, 9 worse).
       It ships.
     - CPU (≤ 600M parameters): bge-v2-m3 on the hybrid, +14.6 [8.8, 20.7].
  2. **The CPU choice failed its latency step.** int8 ONNX exports were made on the Kaggle CPU
     (`tools/kaggle/rerank_export_kernel.py`, per-tensor and per-channel), and int8 bge-v2-m3 kept its accuracy
     (per tensor .594 against .601). But rerank-50 on this 6-core host took **35 s** p50 for bge-v2-m3 and **5.0 s**
     for mMiniLM, the smallest model. gte-ml's int8 lost its accuracy (.457; per channel .070). The rule's step 4
     ("if p50 exceeds 1,000 ms, the best allowed model under 1,000 ms") had no model to take.
  3. **An addendum, written before any of its scores existed**
     (`evals/results/rerank-rule-addendum-cpu-2026-11-20.json`). Cost scales with tokens scored, so it searched
     int8 mMiniLM over passage length {400, 800, 1,600} × depth {10, 20, 30, 50}, on this host, through the served
     reranker. It takes the best NDCG@10 + MRR@10 with p50 ≤ 1,000 ms, shipping only if its CI against unreranked
     clears zero (`evals/rerank_budget.py`). Under the ceiling: 400 × 10/20/30 and 800 × 10. Chosen: **800 × 10**,
     .512 / .491 at p50 589 ms, p95 912 ms; +5.8 NDCG@10 [1.1, 10.6] (29 better, 12 worse). 400 × 20 was .509 / .464.
- Measured on the served path (`evals/lexical_benchmark.py --impls hybrid,ranked`, paired by `evals/served_paired.py`;
  GPU question vectors and reranker scores replayed from the Kaggle runs; provisional, golden sets are drafts, κ not
  measured). The test split was scored once, after the freeze:

  | | dev NDCG@10 / MRR@10 | test NDCG@10 / MRR@10 | test Δ NDCG@10 (ranked − hybrid) |
  |---|---|---|---|
  | cpu hybrid → ranked | .454 / .412 → **.512 / .491** | .376 / .330 → **.449 / .431** | +7.3 [2.0, 12.6], 19 better / 6 worse |
  | gpu hybrid → ranked | .573 / .524 → **.832 / .802** | .531 / .471 → **.775 / .738** | +24.4 [16.2, 32.9], 41 / 8 |

  - GPU test recall@10 goes .750 → .931 (the citations + dense slate), and recall@50 .951 → .972. Roman Urdu NDCG@10
    goes .455 → .759 (6 cases). On the CPU, Roman Urdu stays 0 (no CPU generator reads it).
  - The served results equal the slate evaluation's to the fourth decimal (dev CPU .5123, test GPU .7751). The
    reranker the eval scored is the one serving runs.
  - **Latency.** CPU rerank p50 682 ms dev and 684 ms test (p95 1.2–1.3 s), passage read included; ranked total
    p50 1.5 s. The 8B model's own serving latency is **not measured**:
    - on a T4 at 50 pairs in one batch, the kernel's latency step ran out of memory (after the scores were saved);
    - a 64-pair smoke run took 20.8 s;
    - it needs measuring on the real GPU host, with TEI or vLLM batching.
    The served GPU rows replay scores, so their 157 ms rerank time is only the passage read. docs/04's 60 ms budget
    for rerank-50 is not met by any model here. At these passage lengths (median 330 tokens a pair), even a
    MiniLM-class model is about 100 ms a pair on a CPU core group.
  - **int8 scores depend on their batch-mates.** Dynamic quantisation scales activations per batch: batch 16 against
    batch 1 differ by 0.17 mean absolute (logit units). The dev numbers were scored with serving's own batching
    (16 within a question). `tests/test_reranker_model.py` checks agreement with fp32 (correlation > 0.98), not
    equality.
  - A first served GPU run on a cold cache gave p95 6.2 s; the warm rerun is the one kept. The first arm of each
    test run still shows the cold start: hybrid p95 7.3 s on the GPU test run.
- Why: accuracy first (owner). The GPU profile gains about 25 NDCG@10 points on both splits with intervals well clear
  of zero; the CPU profile gains about 6–7 within a 1 s budget. bge-v2-m3 (+14) is what a CPU host fast enough for it
  would serve: about 35× this host's throughput, or a GPU. Fine-tuning (docs/04 §5.1, ADR-2) waits for annotated
  golden-set labels.
- Not done here, recorded as open: the gate's degraded-mode calibration (an `unreranked` result must abstain until
  it ships, docs/04 §9.2: the gate is the next slice); ADR-1d after reranking; 8B serving latency.
- Where:
  - nizam/retrieval/rerank.py (ranked, rerank, SLATE_WINDOWS, RERANK_INPUT); nizam/inference/reranker.py
    (OnnxReranker, RemoteReranker); nizam/retrieval/lexical.py (`rerank_score`, `windows`);
    nizam/retrieval/candidates.py; nizam/storage/unit_search.py (unit_passages);
  - tools/kaggle/{rerank_kernel.py, rerank_export_kernel.py, kg.sh}; tools/rerank_bundle.py (the GPU reference
    bundle, `models/reranker-gpu`);
  - infra/scripts/{encoder-bundle.sh, export.sh, export-physical.sh} (both rerankers travel with SHA256SUMS;
    restore installs them);
  - evals/{rerank_slates.py, rerank_eval.py, rerank_budget.py, precomputed_reranker.py, served_paired.py,
    lexical_benchmark.py};
  - evals/results/rerank-rule-*.json, rerank-dev-2026-11-20.json, rerank-test-gpu-2026-11-20.json,
    rerank-cpu-budget-dev-2026-11-20.json, {dev,test}-ranked-{cpu,gpu}-*.json;
  - tests/{test_rerank.py, test_rerank_eval.py, test_reranker_model.py};
  - docs/04 §5 and §9 (as built).

### D-100 · 2026-11-19 · New source drops and every leftover scan wait until retrieval is finished
Area: owner ruling, corpus, process · Status: standing
- Decision: the owner ruled that the source drops of 16 Nov in `E:\nizam-data`, and everything else left over, are
  written down and decided only when L3 retrieval is finished.
  - The 16 Nov drops are: FBR codes and Customs SROs, SECP, PSX, and the Supreme Court, Lahore, Peshawar and Sindh
    High Court judgments.
  - The leftovers are: the 26 GB Assembly Acts, the 874 AJK and 151 GB scans, and the 66 acquisition exceptions.
  - "Finished" means the reranker, the calibrated gate and context assembly (docs/04), with the golden set scored on
    the frozen test split.
  - Until then nothing from them is landed.
- What was measured first, so the decisions start from facts:
  - every file's SHA-256 against `blob`;
  - its title and year against the 10,342 released laws (federal-only for FBR, SECP, PSX and Customs);
  - each PDF's text layer.
- Findings:

  | Source | Distinct files | Text / scan | Against the corpus |
  |---|---:|---|---|
  | FBR codes | 178 | 153 / 25 | 132 files are other versions of 39 held laws (24 Customs Act consolidations); 34 new |
  | FBR Customs SROs | 89 | 78 / 11 | 80 new |
  | SECP | 1,322 | 925 / 383 | 105 files of 53 held laws; 1,177 new, including 214 circulars, guidelines and directives |
  | PSX | 150 | 115 / 26 | all new |
  | GB code (12 Sep) | 19 | 3 / 16 | covers the 26 GB exceptions (official links 404); 2 text laws are new |

  - **Judgments:** about 69,000 files, none held: SCP 3,750, LHC 4,557, PHC 5,713, SHC 55,123 HTML.
  - **The Peshawar zip is a bundle.** It holds byte-identical copies of the other zips; only its Peshawar judgments
    and an SRO folder (the same 89 files as `fbr_Customs.zip`) are unique.
- Why: the build order (CLAUDE.md; the `nizam-workflow` skill).
  - New laws, regulator material and OCR'd scans would move the golden-set numbers while the reranker and gate are
    being tuned against them.
  - Judgments need a pipeline docs/03 and docs/06 plan but nothing has built: judgment tables, citator,
    `invalidated_by`.
  - Two questions need design first and are not settled by the docs: how a dated whole-law consolidation becomes
    provision versions without breaking citations (INV-4, INV-5); and whether non-binding regulator guidance belongs
    in the corpus at all.
- Where: docs/DEFERRED-SOURCES.md (each item, its counts, the decision needed and a recommended option);
  `tools/evidence/source-drops-2026-11-19/` (per-file verdicts, text-layer results, the scripts); this log's open questions.
  Entry D-099 is reserved for the GPU embedding generation, in progress the same day.

### D-099 · 2026-11-20 · A second dense space: Qwen3-Embedding-8B sign bits for the GPU host, bge-m3 kept for the CPU
Area: owner ruling, L2 storage, L3 retrieval, evaluation · Status: standing (docs/03 §3, docs/04 §4.2, as built)
- Decision: the owner asked for Qwen3-Embedding-8B "end to end", keeping the current embeddings: "we would have diff
  online and offline". Both spaces are now active, one per encoder device:
  - **cpu**, generation 1: bge-m3, `bit(1024)` in `chunk.embedding`, int8 ONNX query encoder on any CPU (D-098,
    unchanged). It serves laptops, a restored teammate database and the offline path.
  - **gpu**, generation 2: Qwen/Qwen3-Embedding-8B @ 1d8ad4ca, `bit(4096)` in `chunk_embedding_gpu`. Its query encoder
    runs on the GPU host that will serve the answer model (`nizam.inference.remote`).
  - `NIZAM_DENSE_PROFILE = gpu | cpu | auto` picks the space; a GPU encoder that cannot load or answer falls back to
    the CPU space, marked `dense_cpu` (docs/04 §9.2). The encoder decides the space, so the two are never compared
    (docs/03 §3: two generations never share a column or an index).
- How it was done:
  1. **Embedded on Kaggle** (`tools/kaggle/embed8b_kernel.py`): two T4s per run, fp16, 512 tokens, last-token pooling,
     the model card's instruct template for questions only. 24 shards of about 47,177 chunks over two accounts (runs
     e8a and e8b), each shard 386 MB of float16.
  2. **Verified before use** (`tools/kaggle/shards.py`): every shard's row count, first and last chunk id and id hash
     match the export; no non-finite row; unit norm; one revision; the dev questions and 256 probe chunks agree across
     the runs and four GPU processes (cosine 1.000000).
  3. **Storage form chosen by a rule written before any 8B corpus vector existed**
     (`evals/results/qwen8b-storage-rule-2026-11-19.json`; owner priority: accuracy first). Kernel-style dense
     evaluation on dev, top 3,000 chunks (`evals/shard_dense_eval.py`):

     | dev, 108 cases | r10 | r50 | MRR@10 | bytes/chunk |
     |---|---|---|---|---:|
     | full float, 4,096 (reference, not stored) | .843 | .940 | .627 | — |
     | **bits4096 (chosen)** | **.866** | **.968** | **.626** | 512 |
     | bits2048 | .838 | .963 | .614 | 256 |
     | bits1024 | .806 | .944 | .591 | 128 |
     | bits1024 → halfvec(1024) rescore @1,000 | .824 | .940 | .610 | 2,180 |

     - bits2048 is within 1 point on r50 but not on MRR@10 (−1.2), so the rule keeps 4,096. Every halfvec-rescored
       arm scored below the bits alone, so no float column is stored (docs/03's "do not retain full precision" holds).
     - Against the other spaces' binary bake-off rows (same cases, same scoring; paired bootstrap, 10,000 resamples):
       r50 +25.5 [17.1, 34.3] over bge-m3 (28 better, 1 worse) and +19.9 [12.0, 28.2] over Qwen3-0.6B. The Urdu
       stratum goes .333 → 1.000 over bge-m3.
  4. **Schema:** 0112 (one active generation per `encoder_device`, `storage`, `vector_dims`, `rescore_dims`) and 0113
     (`chunk_embedding_gpu`: `bit(4096)`, `ON DELETE CASCADE` from `chunk`, jurisdiction copied from the chunk by
     trigger, HNSW `bit_hamming_ops` m = 16, ef_construction = 64). Audit **A22** is its rule: with a GPU generation
     active, every chunk has exactly one vector of it, of its width, from today's chunker, in its chunk's scope; none
     belongs to another generation. 44/44 pass.
  5. **Loaded** by `tools/load_embeddings_gpu.py` in one transaction: 1,132,245 vectors in 8 min 26 s including the
     index (4 min 54 s). Table 636 MB, index 890 MB; the database is 7.9 GB (was 6.3). The loader's COPY named a
     `half` column even when the table has none; fixed before the load.
  6. **Replays:** this host cannot run the 8B encoder. The chunk worker counts a replay's new chunks without a GPU
     vector; A22 fails until they are embedded on Kaggle (`tools/embed_topup.py`, `kg.sh`) and loaded with
     `--topup`, which refuses unless the run is the active generation's model, commit and template and its dev
     questions reproduce the generation's.
- Measured on the served path (`evals/lexical_benchmark.py`, question vectors made by the corpus run and replayed by
  `evals/precomputed_encoder.py`; provisional, golden sets are drafts, κ not measured):

  | | dev r10 / r50 / MRR@10 | test (run once) r10 / r50 / MRR@10 |
  |---|---|---|
  | bge-m3 hybrid | .616 / .764 / .412 | .535 / .743 / .330 |
  | **8B hybrid** | **.745 / .958 / .525** | **.750 / .951 / .471** |
  | 8B dense alone | .889 / .991 / .659 | .826 / .972 / .629 |

  - 8B hybrid − bge-m3 hybrid, r50: dev +19.4 [12.0, 27.3], 22 better / 1 worse; test +20.8 [12.5, 29.9], 17 / 0.
    The rule's last step (keep the GPU generation only if dev hybrid r50 rises) is met.
  - Arabic-script Urdu and Roman Urdu reach 1.0 on both splits (dev 7 + 5, test 2 + 6 cases). Roman Urdu was 0 with
    bge-m3 because no generator read it; the 8B space does without transliteration.
  - **Equal-vote RRF now costs accuracy.** 8B hybrid − 8B dense: r50 −3.2 [−6.9, −0.5] dev, −2.1 [−6.9, +1.4] test;
    MRR@10 −13.4 [−21.7, −5.2] dev, −15.8 [−24.7, −6.7] test. Fusion is left as built (D-098 item 9) and recorded as
    an open question for the reranker slice, which sees the fused slate: tuning it now on 108 dev cases would fit
    noise twice.
  - The test vectors were encoded once, after the configuration was frozen (`kg.sh q8push`, run q8t1); its
    re-encoded dev questions match the corpus run's at cosine 0.999997, so they are the same space. Query encoding is
    88 ms p50 on a T4, batch 1. Served latency above excludes it: hybrid p50 761 ms dev / 970 ms test, p95 1.4–2.0 s.
- Why: accuracy first (owner). Recall@50 rose by about 20 points on both splits with intervals clear of zero, the
  Urdu and Roman Urdu gaps closed, and the cost is 1.5 GB of disk and a GPU at query time, which the answer model
  needs anyway. bge-m3 is kept because a CPU-only host must still have dense search.
- Where:
  - infra/postgres/migrations/0112–0113; tools/audit/criteria.sql (A22); tools/load_embeddings_gpu.py,
    tools/embed_topup.py;
  - tools/kaggle/{embed8b_kernel.py, query8b_kernel.py, shards.py, kg.sh};
  - nizam/inference/remote.py; nizam/storage/unit_search.py; nizam/retrieval/candidates.py; nizam/workers/chunk.py;
  - infra/scripts/{encoder-bundle.sh, export.sh, export-physical.sh} (the GPU encoder's reference bundle travels with
    SHA256SUMS);
  - evals/{shard_dense_eval.py, precomputed_encoder.py, lexical_benchmark.py}; evals/results/qwen8b-*,
    *-gpu-2026-11-20.json, *-paired-*-2026-11-20.json;
  - tests/{test_gpu_generation_db.py, test_dense_profiles.py, test_remote_encoder.py, test_shard_dense_eval.py};
  - docs/03 §3 and docs/04 §4.2, §5 (as built), docs/SCHEMA.md, docs/CORPUS-CRITERIA.md (A22).

### D-098 · 2026-11-19 · The dense slice: bge-m3 sign bits, HNSW, and hybrid candidates fused across generators
Area: L2 storage, L3 retrieval, evaluation · Status: standing (docs/04 §4.2, §5, R1's dense half, as built)
- Decision:
  1. **A golden split, frozen before any model was scored** (`evals/golden/split.py`, `split-v1.json`):
     - dev is 120 cases, 108 of them answerable; test is 80 cases, 72 answerable.
     - Every choice below was made on dev only. Test ran once, after the configuration was frozen (docs/10).
  2. **Model: BAAI/bge-m3 at commit 5617a9f6**, chosen on dev from three models. Each embedded all 1,132,245 chunks
     on a Kaggle T4 (`tools/kaggle/embed_kernel.py`; fp16, 512 tokens, `context_prefix + "\n" + span`):

     | dev, 108 cases | full r10/r50 | binary r10/r50 | binary − full r50, 95% CI | Urdu (Arabic script) binary r50 | GPU time |
     |---|---|---|---|---|---|
     | bge-m3 | .653/.768 | .620/.713 | −5.6 [−12.0, +0.5] | .571 | 1.5 h |
     | multilingual-e5-large-instruct | .634/.745 | .407/.565 | −18.1 [−28.7, −7.9] | .500 | 1.5 h |
     | Qwen3-Embedding-0.6B | .676/.792 | .662/.769 | −2.3 [−7.4, +2.3] | .429 | 4.0 h |

     - The choice was to be scored on recall and the Urdu–English gap. Qwen's overall lead over bge-m3 in binary is
       not significant: r50 +5.6 [−2.8, +13.9], paired.
     - Qwen's Urdu deficit points the same way on the Arabic-script cases and the Urdu stratum (.25 vs .33). It
       doubles the Latin−Urdu gap (0.40 vs 0.19).
     - In the hybrid, lexical already serves English, and Urdu-script questions get nothing from it (r50 0.0), so
       dense is their only path.
     - multilingual-e5's mean-pooled vectors are anisotropic and lose 18 points as sign bits.
     - Pooling is read from each model's own `1_Pooling/config.json` at the pinned commit. The first full run died
       after embedding the corpus on a sentence-transformers method that no longer existed; now every kernel edit is
       smoke-tested.
  3. **Storage: the sign bits only** (`bit(1024)`, `np.packbits(v > 0)`), as docs/03 settled. Asymmetric rescoring,
     the float query against the stored ±1 bits over a Hamming shortlist, was measured
     (`evals/binary_ablation.py`): it is not consistently better for bge-m3 (r50 .782/.722/.750 at 300/1,000/3,000
     chunks, r10 .611 vs .630), so it is not built.
  4. **ADR-1d is not yet decidable, and is recorded as a gate on the reranker slice.**
     - It allows binary if it costs ≤2 NDCG points *after reranking*, and no reranker exists.
     - Dense-only, binary costs bge-m3 r50 −5.6 (CI includes 0) and MRR@10 −7.9 [−13.6, −2.4] (a real loss).
     - When the cross-encoder lands, the ablation re-runs after rerank. If binary still costs more than 2 points,
       the fallback is halfvec, or Qwen3's binary-friendly space.
  5. **Schema** (`0109`–`0111`):
     - `embedding_generation` records model, commit, pooling, query template, quantisation, chunker and the
       selection evidence. One row is active (partial unique index). The loader writes the bake-off numbers and the
       paired CIs into `selection`.
     - `chunk.embedding` stays nullable, refining D-095. The rule is audit **A21**: while a generation is active,
       every chunk has its vector, none comes from another chunker, and each sits in its provision's scope.
     - `chunk.jurisdiction` (0110) is set by trigger from the provision path. It is the part of docs/04 §4.2's
       search projection that the dense scan needs, so the scope filter runs inside the HNSW scan. Validity and
       territory stay with the INV-5 gate.
     - `ix_chunk_hnsw` (0111) is HNSW `bit_hamming_ops`, m = 16, ef_construction = 64. It took 3 min 28 s and is
       464 MB. Loading took 59 s; after VACUUM FULL, chunk is 448 MB and the database 6.3 GB.
     - 0109's comment says the index "follows in 0110". It is 0111, because 0110 became the jurisdiction column.
       Applied migrations are not edited.
  6. **Query encoder** (`nizam.inference`, the shared inference worker, import-linted as a leaf):
     - bge-m3 exported to int8 ONNX by dynamic per-channel quantisation (`tools/kaggle/export_kernel.py`).
       Per-channel beat per-tensor on the pre-set rule, r50 first.
     - Against fp32: cosine .989 mean (.978 min), sign bits 95.0%. Dev recall with int8 query bits is .611/.736,
       against .630/.708 for fp32.
     - This host reproduces the export's vectors: cosine >0.999 (`tests/test_encoder_model.py`).
     - It is 570 MB, loads in 23 s, needs 1.1 GB RSS, and encodes in 57 ms p50 on 2 threads.
     - **This deviates from docs/04's ≤20 ms query-embedding budget.** It is mostly hidden by item 9: the request
       waits on the dense job 42 ms p50.
  7. **Dense execution** (docs/04 §9.1):
     - HNSW runs with `iterative_scan = strict_order` and `ef_search` = the window (900 chunks for 300 provisions).
       It returns 0.79 of the exact nearest window (tie-aware, min 0.35) in 39 ms.
     - The exact scan of the smallest real scope (fed alone, 503,746 chunks) takes 147 ms p50 on 5 processes.
     - At the unit level HNSW loses nothing: hybrid r50 .759 against .750 exact.
     - The exact path costs about 0.29 ms per 1,000 chunks, so it breaks even with HNSW near 120,000 chunks.
       `EXACT_SCAN_CHUNKS` stays 120,000, overridable per host by `NIZAM_EXACT_SCAN_CHUNKS`
       (`evals/dense_scan_benchmark.py`).
  8. **Collapse clamps the second best at 0** (docs/04 §5's `max + 0.15 × second best`).
     - Dense scores had been −Hamming distance, so every unit with a second matching chunk was pushed *down*. Dev
       dense r50 was .449, against the kernel's .713 on the same vectors.
     - Dense now scores `1 − d/512`, the cosine of the two sign vectors, and the clamp makes a second match evidence
       only. Dense r50 is now .782.
     - BM25 scores are positive, so lexical rankings are unchanged. A regression test holds it.
  9. **RRF across generators, one vote each.** docs/04 §5 fuses "the four score distributions", meaning the
     generators. The lexical generator's own fusion (body, heading and title, D-097) is one ranked list and dense is
     another, fused with k = 60.
     - Feeding body, heading and title in beside dense gave BM25 three votes, and the hybrid scored below dense
       alone (r50 .759 vs .782). Fused across generators: r10 .588 → .616, r50 .759 → .764.
     - **The generators run in parallel.** The dense job (encode, then its own read-only session) starts on a worker
       thread, and fusion waits for it only once the lexical windows are done.
     - Hybrid latency on dev fell from 1,191/2,065 ms to 761/1,014 ms (p50/p95) with recall identical.
  10. **Degradation** (docs/04 §9.2): only a typed `DenseUnavailable` serves `lexical_only`, marked in the result and
      the trace. That covers a missing encoder, no runtime, no active generation, or an encoder from another space.
      Any other error is an error (tests).
  11. **Operations:**
      - `./nz export` and `./nz restore` ship and verify the encoder (SHA256SUMS).
      - The chunk worker embeds a replay's new chunks on the CPU in the same transaction, and refuses `--rebuild`
        while a generation is active (re-embedding is a rebuild, docs/03).
      - **D-097's "import-linter keeps all six contracts" was measured with a filtered configuration.** The
        committed `.importlinter` failed as is, on modules not yet built. `./nz layers` (`tools/lint_layers.py`)
        runs it, leaving out absent modules and naming them: 7 contracts kept, including the new inference-is-leaf.
- Measured, provisional (drafts, κ not measured; evals/results/*-2026-11-19.json):
  - **Dev:**
    - fused lexical → hybrid, r10 .421 → .616 and r50 .519 → .764;
    - r50 +24.5 [16.7, 32.9], 27 cases better and 0 worse;
    - Arabic-script Urdu 0/0 → .571/.571, and the Latin−Urdu r50 gap .583 → .247.
  - **Test, run once:**
    - r10 .354 → .535 and r50 .542 → .743;
    - r50 +20.1 [11.1, 29.9], 15 better and 1 worse;
    - hybrid − dense r50 +6.9 [−0.7, +14.6].
  - **Roman Urdu stays at 0 on dev (5 cases).** No generator reads it yet (docs/04's transliteration step).
  - **Latency:**
    - hybrid p50 761 ms (dev) / 968 ms (test) and p95 1,014 / 1,465 ms;
    - the lexical path alone measured 792/1,136 and 800/1,278 in the same runs, so the host's run-to-run spread is
      large;
    - p50 is under the ~1 s goal and p95 is not. The largest stages are the INV-5 gate (~350 ms p50) and the
      lexical windows, which the lexical path already had.
- Why: the owner asked for the dense slice end to end, kept only if dev recall rose and the Urdu gap shrank, with
  latency re-measured. Recall rose by 20–25 points with intervals clear of zero on both splits, and the Urdu gap
  more than halved.
- Where:
  - infra/postgres/migrations/0109–0111; tools/audit/criteria.sql (A21); tools/load_embeddings.py;
  - nizam/inference/encoder.py; nizam/storage/{unit_search.py, chunking.py}; nizam/workers/chunk.py;
  - nizam/retrieval/{lexical.py, candidates.py};
  - tools/kaggle/{embed_inputs.py, embed_kernel.py, export_kernel.py, query_kernel.py, kg.sh};
  - evals/{lexical_benchmark.py, binary_ablation.py, paired_bootstrap.py, dense_scan_benchmark.py}, evals/golden/split*;
  - tests/{test_embeddings.py, test_encoder_model.py}; .importlinter, tools/lint_layers.py, nz (`layers`);
  - infra/scripts/{export.sh, restore.sh};
  - docs/03 §3–§4, docs/04 §4.2 and §5 (as built), docs/SCHEMA.md, docs/CORPUS-CRITERIA.md (A21).

### D-097 · 2026-11-19 · L3's first slice: fused lexical units, place territory and the citation fast path
Area: L3 retrieval (and L2 reads) · Status: standing (docs/04 R0 and R1's lexical half, as built)
- Decision:
  1. **`nizam/retrieval/`**, L3's first code. It calls only L2's `nizam/storage/unit_search.py`; import-linter keeps
     all six contracts.
     - The INV-4 contract named a module that does not exist (`nizam.storage.chunks`); it now names
       `nizam.storage.chunking` and `nizam.workers.chunk`.
     - The driver contract now allows indirect imports, so it catches a raw driver import above L2, which is what it
       says it guards.
  2. **Query understanding** (`query.py`):
     - **Citations** (`citations.py`) are resolved from records only (INV-1).
       - The law is a served law matched by its recorded title, federal first, then the most relied-on (D-075).
       - The label is looked up in that law and its same-titled copies only. A territorial copy is returned as an
         alternate; a different law is never consulted.
       - A missing law, or "Article 199" or "the Act" alone, is a typed ambiguity. So are CPC Orders and Rules, which
         this grammar does not read as sections.
     - **The territory** a place names (`places.py`) applies only when the caller gave no scope. It draws on 170
       districts and the province names, read from Wikipedia's district lists on 18 Nov. Two territories in one
       question set none.
     - **The question frame is stripped only from a sentence.**
  3. **Fused candidates** (`lexical.py`):
     - Resolved citations go first.
     - Then RRF (k = 60) of body units and heading units (max + 0.15 × second best, docs/04 §5), plus a title term.
     - Then the INV-5 gate: `operative_provision` is asked only about the top units, in batches, until k remain.
       Filtering never reorders, so the result equals filter-then-rank.
     - The cheap windows are pre-filtered to active provisions in the asked jurisdictions. The view check on a whole
       2,000-id window took 1.3 s; on the top units it takes milliseconds.
     - Per-stage timings go into the trace for INV-3.
  4. **pg_search 0.25.6 drops its match filter under a generic plan.** psycopg prepares a statement after 5 runs, and
     Postgres switches to a generic plan after 5 more.
     - Reproduced: a title matching nothing returned 0 rows ten times, then 5 arbitrary rows.
     - Every pg_search session now sets `plan_cache_mode = force_custom_plan` (both unit_search and the lexical port).
       A regression test holds it.
     - The BM25-stage experiment's E3 (evals/lexical_experiments.py, commit 02a82bc) ran on one long connection, so
       its title term was affected and its 0.564 is not reliable. The shipped figures below come from a fresh
       session per question.
- Measured, provisional (golden sets 1–4, 180 questions, drafts, κ not measured; evals/results/*-2026-11-19.json):
  - **Scoped** (the case's jurisdiction):
    - recall@50: 0.383 → 0.528, a gain of +0.144 (95% CI +0.081 to +0.208);
    - recall@10: 0.219 → 0.394;
    - MRR@10: 0.114 → 0.235;
    - by group, citizen 0.20 → 0.45 and professional 0.73 → 0.81;
    - latency p50 606 → 674 ms, p95 711 → 864 ms.
  - **Unscoped** (places only): recall@50 0.283 → 0.494, a gain of +0.211 (CI +0.147 to +0.275).
  - **Golden citations** (evals/citation_resolution.py, 224 queries): 220 exact, 4 with their territorial alternate,
    0 unresolved, 0 wrong. That meets R0's "100% resolution or typed ambiguity".
  - **Urdu script** is unchanged at 0.10: the lexical index is English, and that gap is the dense slice's.
- Why: the owner asked to ship the measured fusion and the first query-understanding step without hurting the
  non-functionals much. Recall rose by 14–21 points; latency rose by 9% at p50 and 22% at p95.
- Where:
  - nizam/retrieval/{query.py, citations.py, places.py, lexical.py}; nizam/storage/unit_search.py;
  - nizam/storage/lexical.py (custom plans); .importlinter;
  - evals/{lexical_benchmark.py (fused, --unscoped), citation_resolution.py};
  - tests/{test_query_understanding.py, test_retrieval_db.py};
  - docs/04 §4.1 (as built).

### D-096 · 2026-11-18 · The AJK Interim Constitution Act, 1974 is acquired and staged, not yet landed
Area: L1 corpus/acquisition · Status: standing (replaces the open question's "not landed" with what is held and why)
- Decision:
  - **Acquired.** The Act is acquired from the AJK Law Department's own file
    (https://law.gok.pk/wp-content/uploads/2023/10/AJK-interim-constitution.pdf).
    - The host refused connections on 18 Nov, so the bytes come from the Internet Archive's capture of that URL
      (20260512192307) through tools/acquire/stage_wayback.py.
    - They were accepted only because their SHA-1 equals the archive's recorded digest (JJYCI6B5…). Three captures
      from Aug 2024 to May 2026 share it, so the official file has not changed.
    - sha256 5901ea06…, 115 pages.
  - **No OCR is needed for the law.** Pages 12–115 carry the Act in a text layer ("THE AZAD JAMMU AND KASHMIR INTERIM
    CONSTITUTION, 1974 [31st AUGUST, 1974] ACT VIII OF 1974 PREAMBLE…"). Pages 1–11 are scanned front matter (cover,
    Preface, contents) and are not law.
  - **The title** is set from what page 12 prints, because the file name says only "AJK interim constitution".
  - **Not landed.** preflight_segment predicts `blocked`:
    - 33 repeated-label units the default segmenter leaves unsettled;
    - character recall and precision 1.0, quality passed.
    The owner's rule lands nothing that would sit held, so the law waits for its structure to be read.
- Why: it is AJK's constitution and its most important law. The earlier note said only "not landed"; it is now held
  as evidence, and the step left is named exactly.
- Where: tools/evidence/close-2026-11-18/ajk-ic/{staged.csv, preflight.csv} (the bytes: .artifacts/close-2026-11-18/ajk-ic/stage/files/, re-fetchable from the capture); open question below.

### D-095 · 2026-11-18 · Retrieval storage: the chunk table, the lexical indexes and the lexical port
Area: L2 storage · Status: standing (the next slice CLAUDE.md named; docs/03 §3 and §5 as built)
- Decision:
  1. **`chunk`** (0108), as docs/03 §3: offsets into one `provision_version.text_normalised`, `context_prefix`,
     `bit(1024)` embedding.
     - `embedding` is nullable until the dense slice backfills it.
     - A `chunker` column names the splitting rule.
     - A trigger refuses a span past its text.
     - Rows exist for released versions only. `nizam.workers.chunk` builds and keeps them (`./nz chunk`, post-replay
       step 4c), and audit A20 asserts the boundary, span order and coverage.
     - Built: 1,132,245 chunks over 1,114,427 versions, 299 MB, 103 s. A second run writes nothing.
  2. **Chunking as built.** A version holds its own node's words only, so a chunk spans within one version.
     - docs/02 §5.3's "group of adjacent clauses" becomes retrieval's collapse to the unit (docs/04 §5).
     - "Never split a proviso … from the rule it qualifies" becomes `qualifies: <the parent's opening words>` in the
       embedded prefix, never in the quoted text.
     - Spans are at most 1,200 chars, cut at a sentence end, then ';'/':', then ',', then a space. Citation
       abbreviations ('s.', 'No.', 'Rs.') are not sentence ends. Text is single-line (schedule rows flattened), so
       "row-aware" means cutting at the punctuation between rows.
  3. **Lexical indexes**, pg_search pinned at 0.25.6 (the migration refuses another version):
     - body BM25, stemmed English;
     - heading, marginal note and space-folded label;
     - instrument titles;
     - the portable GIN over the tsvector expression.
     They cover every row, and reads filter through the release and operative views.
  4. **The lexical port** (`nizam/storage/lexical.py`, docs/03 §5): `search(q, filters, k)` with as_of mandatory.
     - Implementation A is BM25, B is ts_rank_cd as written, and B′ is ts_rank_cd over any term.
     - BM25 also offers `headings` and `labels`; '462I' finds the printed '462 I' (D-094).
     - Candidates are read through `operative_provision` in two steps: the index's window, then the view asked about
       those ids. A one-statement join planned the whole view (27 s); two steps take about 0.1–1 s.
     - The window widens until k operative candidates are found. Candidates are provisions, never chunk ids (INV-4).
  5. **The benchmark docs/03 §5 requires**, provisional (drafts, κ not measured). Golden sets 1–4, 180 answerable
     cases, raw questions, k = 50:
     - BM25: recall@50 0.383, recall@10 0.219.
     - B as written: 0.022 (no result for 159 of 180 questions, since every word is required).
     - B′: 0.061 (p50 2.5 s, p95 6.2 s).
     The large delta justifies self-hosting pg_search, by docs/03 §5's own rule.
  6. **Reviewed by schema-reviewer before commit; every finding fixed or recorded:**
     - B′ re-stemmed its query, so 'provisions' became 'provi' and the term was silently dropped. It now casts
       instead of re-parsing (regression test) and was re-measured: 0.056 became 0.061.
     - The subtree cap now counts nodes, not version rows: a much-amended node could otherwise fill it.
     - `labels()` came back in arbitrary uuid order. It is now in instrument and printed order, with an optional
       instrument filter.
     - Results carry `truncated` when the window cap is hit (INV-3).
     - A datetime is refused as `as_of`.
     - Chunk whitespace is ASCII-only, the same class A20 checks. Measured: 0 versions hold other spaces, so the
       output is unchanged.
     - LIMIT is a bound parameter.
     - Recorded for production: build the indexes CONCURRENTLY in their own files (checking that pg_search
       supports it first), and REVOKE writes from the application role. That role does not exist yet.
- Why: CLAUDE.md named "the chunk table and BM25 index" as the next slice. Dense embeddings, fusion, the gate and L3's
  query understanding follow in their own slices (docs/04 §11 R1), against the recall floor measured here.
- Where:
  - infra/postgres/migrations/0108_chunk_and_lexical.sql;
  - nizam/storage/{chunking.py, lexical.py}; nizam/workers/chunk.py;
  - tools/audit/criteria.sql (A20); tools/post_replay_sequence.sh (4c); nz (`chunk`);
  - evals/lexical_benchmark.py, evals/results/lexical-2026-11-18.json;
  - tests/{test_chunking.py, test_chunk_and_lexical_db.py};
  - docs/03 §3 and §5 (as built), docs/SCHEMA.md, docs/CORPUS-CRITERIA.md (A20).

### D-094 · 2026-11-18 · Open questions closed by decision: word amendments, repeals by subject, undated amendments, "462 I", the 23rd–24th Amendments, Gilgit-Baltistan heritage
Area: corpus/legal model · Status: standing
- Decision:
  1. **Amendments of words are amendments, not repeals.** "For the word X, the word Y shall be substituted" changes a
     provision's text. Where the amending law is held, it is served as a provision version (INV-5). It is never a
     unit repeal (0102 stays unit repeals only).
  2. **A repeal by subject is not resolved to units.** Clauses such as "any law inconsistent with this Act is
     repealed" or "all laws relating to X" name no unit. Applying them would be the guess the corpus rules forbid.
     Such laws keep the owner's presumption that a law is in force (16 Nov), and no `repeals` edge is drawn.
  3. **Undated amendments stay served from the capture date** (3,856 laws, `text_known_from`, 0096–0099). The rule is
     "never guess a version boundary"; serving the earlier text as at an earlier date would be that guess. The number
     falls only as dated amending instruments are held. This is the correct behaviour, not a backlog.
  4. **"462 I" is kept as printed.** PPC p159 (doc 4441) prints "462 I." with a space; "462J." follows without one.
     docs/01 keeps labels verbatim ("365 A"). Matching "462I" to it belongs to retrieval's citation lookup
     (docs/04), which normalises spacing.
  5. **The 23rd and 24th Amendment Acts are not landed.** Searched 18 Nov:
     - The only official copy of the 23rd is the National Assembly's upload of the Bill (na.gov.pk 1490160955_216.pdf,
       22 Mar 2017). It is a scan with an OCR text layer, not the assented Act, so the owner's rule on scans applies.
     - No official copy of the 24th was found.
     - Both amendments' effect is in the consolidated Constitution as modified to 22 Dec 2017 (na.gov.pk
       1515056252_668.pdf).
  6. **No Gilgit-Baltistan heritage law exists** to land (D-085). The heritage tab shows GB's crafts without a law.
     Revisit only when the Assembly enacts one.
  7. **The released-count guard reads counts that a prune cannot invalidate.**
     - claude-baseline-89 stored instrument ids, which the guard resolved through `instrument`. After the D-086 prune,
       about 1,100 of those ids were gone, and 959 laws read as undeclared rises.
     - The guard now prefers a baseline's `released_counts.json` (document → count), written at signing
       (`--record-documents`). It refuses (exit 2) a baseline whose ids no longer resolve instead of miscounting.
     - claude-baseline-90 is signed at 10,342: 10,342 → 10,342, with 0 undeclared.
- Why: the owner asked that every open item except the scans be closed correctly. These are decided by the existing
  rules and invariants, not by new corpus work.
- Where: tools/released_count_guard.py; .artifacts/release-work-2026-09-24/claude-baseline-90/; this entry.

### D-093 · 2026-11-18 · The local S3 stand-in is SeaweedFS
Area: L2 storage/deploy · Status: standing (closes D-088's open question)
- Decision: the compose service `blobstore` runs `chrislusf/seaweedfs:4.51`, pinned by digest (sha256:f7a49e3f…,
  26 Oct 2026). It sits under the `blobstore` profile until code uses it, on localhost:9000.
  - Credentials come from infra/.env MINIO_ROOT_USER and MINIO_ROOT_PASSWORD. The names are kept so existing .env
    files, the bootstrap and the kit still apply.
  - The S3 identity file is written inside the container at start, from those variables.
  - The healthcheck requires that an unsigned request be refused.
- Why:
  - **Candidates, checked 18 Nov on Docker Hub and GitHub, not recalled.** All four are active and pull anonymously:
    - SeaweedFS: Apache-2.0, 43.6M pulls, pushed 18 Nov.
    - RustFS: Apache-2.0.
    - versitygw: Apache-2.0.
    - Garage: AGPL-3.0, a heavier licence obligation for no gain here.
  - **Proven on the pin with SigV4-signed requests, the signing R2 requires:**
    - create bucket, put, get, list and delete succeed;
    - unsigned and wrong-secret requests are refused (403);
    - the compose service comes up healthy with the .env credentials, and `./nz status` and the selftest see it.
- Where: infra/compose.yaml (`blobstore`), infra/scripts/selftest.sh, nz, infra/README.md, SETUP.md,
  docs/09a (as built, 18 Nov), tools/evidence/close-2026-11-18/{s3_roundtrip.sh, blobstore_up.sh}.

### D-092 · 2026-11-18 · Title-region recorders read the law as page-read
Area: L1 corpus · Status: standing (closes the open question "Title-region recorders read raw OCR")
- Decision: `record_instrument_numbers`, `record_long_titles` and `record_enacted_dates` read their window with the
  observation's active page-read corrections applied (tools/title_region_text.py). It uses the segmenter's own
  `_apply_curation_patches`, one correction at a time.
  - A correction whose block is outside the window is not applied.
  - One the window cannot apply whole (a two-block label move) is skipped, never half-applied.
  - `--raw-text` reproduces the old reading.
- The corpus-wide dry run the question asked for, raw text against page-read text:
  - **Numbers:** 42 new (for example "ACT No. XVII OF 1876" in hand-read scans whose raw OCR printed none), 1
    withdrawn.
  - **Long titles:** 101 new, and 6 withdrawn (OCR garbage such as "An Act for regula Iu we pepe Sal…").
    - 9851's raw title came from the wrong text: its reading shows the Indian Tariff Act, 1934.
    - 9546's reading runs past the window, so its title is left unasserted rather than taken from the raw OCR.
  - **Enactment dates:** 68 new and 6 withdrawn. 37 of the new dates disagree with the portal's dates, which are
    known to be unreliable (L2 metadata note, 12 Nov).
  - Applied. `apply_instrument_metadata` kept the segmenter's number in its 2 conflicts (9583, 9748). The repeal
    re-derivation updated 1 instrument. Serving was refreshed; the audit passes 41/41.
- Why: the page reading is the authority for a scan read by hand (the owner rule, D-076). The raw OCR is not.
- Where: tools/title_region_text.py; the three recorders (`--raw-text`, and `--dump` on long titles);
  tools/evidence/close-2026-11-18/{recorders_ab.sh, recorders/, recorders_apply.sh}.

### D-091 · 2026-11-18 · Rebuild drift reviewed law by law, and the verdicts enforced
Area: L1 corpus/process · Status: standing (closes the open questions "Older rebuild drift" and "Rebuild drift found by the D-080 A/B")
- Decision: every law the open questions named was dry-run as it stands, multi-instrument documents through the
  materializer's own `prepare()`, node by node. Each now carries a verdict in
  tools/evidence/drift-review-2026-11-18.json.
  - **Closed (4).**
    - 2772 rebuilds identically.
    - 8743 differed only in its path prefix and is identical since D-090.
    - 4702 and 9868 are multi-instrument documents that rebuild identically through the materializer. The worker's
      single-expression dry run was the wrong judge.
  - **The release is right and the rebuild worse (12).** Laws: 1101, 1977, 2904, 2491, 8213, 9310, 9659, 5494, 8173,
    6576, 6784, and 4347 expression 3. The rebuilds:
    - split wrapped amendment headings into stray root clauses;
    - take a footnote for s.1's heading;
    - lose Parts;
    - rename "Part I" (printed "I.") to "1";
    - renumber duplicate suffixes;
    - split damaged Gazette text;
    - fold 2491's "14. The Assistant Registrar" into item 13, so its reviewed reparent fails closed.
  - **Enforced.** `legal_write.save` and `save_many` now refuse an APPROVED release change for a law whose verdict is
    `stored_correct`, quoting the finding. An approval can no longer carry a known-worse rebuild in. Lifting it means
    fixing the regression and recording a new verdict.
- Why: the questions said each law "needs its own review before its next replay". The replay gate already refuses
  unapproved changes. What was missing was the review and a guard against approving through it.
- Consequence: the furniture of 1101, 1977 and 2904 (D-089) waits for their regressions to be fixed.
- Where: tools/evidence/drift-review-2026-11-18.json; nizam/storage/legal_write.py (`_refuse_reviewed_drift`);
  tests/test_drift_guard.py; tools/evidence/close-2026-11-18/{baseline.sh, diffsum.py, prefixdiff.py, multi_compare.py}.

### D-090 · 2026-11-18 · A rebuild keeps its released path prefix (INV-4)
Area: L1/L2 · Status: standing
- Decision: `build()` gives an expression that already has an active tree that tree's path prefix
  (`legal_write.released_path_prefix`).
  - A reviewed identity (multi-instrument plan) still builds its own prefix.
  - `keep_path_prefix=False` asks for the inferred one.
- Why: the number and year the head infers can drift as the parser changes. Act VI of 1874 (doc 8743) rebuilt as
  'y1874_o12229', so every provision was renamed although the catalogue still records VI. Citations are rendered from
  the instrument's recorded number and year (INV-1). The path is an identifier, and INV-4 forbids moving one.
- Where: nizam/workers/segment.py (`build`), nizam/storage/legal_write.py; tests/test_path_prefix_stability.py;
  docs/SEGMENTATION-PROFILES.md.

### D-089 · 2026-11-18 · The furniture left after D-085: 16 of 23 laws cleaned, and set-aside heads that still end a sentence
Area: L1 corpus · Status: standing (closes most of the open question "Page furniture left after D-085")
- Decision:
  1. **AJK (6 laws: 10482, 10499, 10524, 10861, 10870, 10977): all cleaned.**
     - Each had one reading anchored on a footnote line, which the segmenter moves out before readings apply
       ("matched 0 blocks").
     - ajk_folio_patch.py now anchors on law body text only. The 140 folios were re-read, proven and released.
  2. **Sindh (17 laws), round by round under the D-085 proof (no path, kind, label, parent or heading change; only
     head words deleted):**
     - **Clean (7):** 986, 1864, 3880, 3914, 2022, 2339, 3243.
     - **Clean except named pages (5):** 1245 pp3–4, 2505 p4, 2765 pp4–6, 2902 pp3–5, 3992 pp33, 35.
     - **Untouched (2):** 2206 p3 and 3919 pp5–6, every page of which is load-bearing.
     - **Held back by drift (3):** 1101, 1977, 2904 (D-091).
  3. **Generator fixes (sindh_title_patch.py):**
     - The citation printed under the title is head too. 3243 p5 had cut two lines and left "SINDH ACT NO. XXXIX OF
       2023" in the block.
     - A cut is anchored on a line unique on its page, which fixes 986's two-block refusal.
     - Locators avoid every reading ever recorded on the page. The evidence is append-only, and the recorder refuses
       an identical withdrawn reading.
     - An optional pages file emits boundary readings.
  4. **Rule `reviewed_head_boundary` (`source_head_boundary_blocks`).** A set-aside running head that a reading also
     names here still ends the sentence before it, as the printed header did in the released tree.
     - `previous_content` skips furniture, so with the head gone a chapter line after "…of the Institute:" read as a
       cross-reference, and Chapter II was swallowed into clause (xxiii) (3243).
     - Data-gated in every profile. It fails closed on a block not set aside or not in the document.
     - With it, 3243 is clean.
  5. **The 14 remaining pages in 7 laws are a different mechanism.** In 1245 the head's folio text, read into
     s.3(2), was what kept "(4)" a sub-section. The words stay there until each page is read, because removing them
     changes the reviewed structure.
- Where: tools/recrawl/{sindh_title_patch.py, ajk_folio_patch.py, furniture_rounds.py}; nizam/corpus/segment.py
  (`reviewed_head_boundary`); nizam/workers/segment.py, tools/record_curation_patch.py,
  tools/materialize_multi_instrument.py (key registered); tests/test_head_boundary.py;
  tools/evidence/close-2026-11-18/ (round.sh, run_r1-r4.sh, residual-pages.json, every round's readings and proof).

### D-088 · 2026-11-18 · MinIO becomes opt-in: its public image can no longer be pulled
Area: L2 storage/deploy · Status: Superseded by D-093 (the service is now SeaweedFS; still opt-in)
- Decision:
  1. The `minio` service in infra/compose.yaml moves behind the Compose profile `blobstore`. `./nz up`,
     `infra/up.sh` and the teammate kit start Postgres and pgAdmin only.
  2. The self-test checks MinIO only where its container exists. `./nz status` names it only then.
  3. The image pin is kept, so a machine that still holds the image can start it with `--profile blobstore`.
- Why: the D-087 kit's first end-to-end run, into a fresh Ubuntu 24.04 on 18 Nov 2026, stopped at
  `pull access denied for minio/minio`.
  - Docker Hub's API returns 404 for the repository.
  - `quay.io/minio/minio` at the pinned digest returns 401 to an anonymous pull.
  - Public reports put the Hub withdrawal in September 2026 and quay's login requirement from about 24 September.
    These are secondary sources (GitHub issues in milvus-io/milvus #53430 and xtdb/xtdb #6061, and blog posts); no
    MinIO statement was found.
  - No code reads or writes the blob store: grep finds MinIO only in selftest.sh. So no machine set up after
    September could run `./nz up`, and the owner's worked only because the image was already cached.
- Where: infra/compose.yaml (minio service comment), infra/scripts/selftest.sh, nz (status), infra/up.sh; open
  question "The local S3 stand-in after MinIO".

### D-087 · 2026-11-18 · The teammate kit: one zip and one script make an exact replica on a new laptop
Area: process/deploy · Status: standing (extends the D-086 transfer; corrects SETUP.md's WSL step)
- Decision:
  1. **The kit.** `tools/teammate-kit/build_kit.sh` packs one zip, with entries stored rather than deflated:
     - the exact copy (`./nz export --physical`), which is the copy that gets restored;
     - the logical dump of the same database. Both must carry the same signature. The dump is used only when the
       exact copy cannot be, as on a non-x86 laptop, where its CPU check refuses;
     - a git bundle of HEAD, so the laptop needs no GitHub access;
     - `observations.csv`;
     - `kit.json` (commit, export names, signature).
     The builder refuses uncommitted infra or code, and a HEAD not yet on origin/main.
  2. **One script, `SETUP-NIZAM.ps1`, resumable.** Each step is skipped when already done:
     - WSL on (one UAC prompt, one restart);
     - `.wslconfig` with vmIdleTimeout, and memory set to half the laptop's RAM (capped at 10 GB; the owner's laptop
       crashed at 10 of 15 GB);
     - Ubuntu 24.04 installed `--location` on the data drive;
     - a Linux account made as root, with its password asked once;
     - code cloned inside WSL, so the checkout has LF endings;
     - `infra/wsl/setup-docker.sh` as root, then `uv sync --extra api` and a fresh `infra/.env` whose CORPUS_ROOT
       follows the chosen drive;
     - the physical restore. It ends with the signature compared, `./nz up`, the 41-criterion audit and the API.
     Windows PowerShell 5.1 runs it with ErrorAction Continue and explicit exit-code checks, because under Stop any
     native stderr line aborts the script.
  3. **Ubuntu is named by version.** `wsl --install -d Ubuntu` now installs 26.04: Microsoft's
     DistributionInfo.json, read 18 Nov 2026, maps `Ubuntu` to ubuntu-26.04.1. `setup-docker.sh` requires noble. The
     kit and SETUP.md install `Ubuntu-24.04` and set NIZAM_WSL_DISTRO, which `nz.ps1` already reads.
- Why: the owner asked for "a zip and a single file that i run on his laptop with that zip [and] everything is set up
  perfectly". SETUP.md path A took nine manual steps, one of which had silently gone stale.
  4. **Proven end to end (18 Nov 2026)** on the owner's laptop, into a fresh WSL distro installed by the script
     from the checksum-verified ubuntu-24.04.5 image, under E:\kit-test.
     - Run 1 stopped at the MinIO pull (D-088).
     - Run 2 stopped on a network timeout. Image pulls now retry six times.
     - Run 3: the exact copy was restored in 60 s, the signature matched, the audit passed 41 of 41 and the API
       answered 200.
     - Run 4 skipped every finished step.
     - Windows' localhost:8080 belonged to another program on that laptop. The closing summary now tests
       localhost, falls back to WSL's address and names the program holding the port.
- Where: tools/teammate-kit/{SETUP-NIZAM.ps1, build_kit.sh}, SETUP.md ("The kit", step 1).

### D-086 · 2026-11-18 · Duplicate links advance after re-materialization; 18 Nov prune and transfer
Area: L2 storage/process · Status: standing
- Decision:
  1. **A new post-replay step 2-dup** (tools/advance_duplicate_links.sql). Step 2 re-materializes the
     multi-expression documents after step 1 has re-linked exact duplicates. That left 44 active duplicate rows
     (docs 1970, 3392, 4497) naming the retired canonical of their own expression, and the retired-revision prune
     refused to run ("retained instrument references a prune target", caught by its isolated proof on a restored
     copy, before anything live was touched).
     - Each such link now advances to the active canonical of the same observation and expression ordinal.
     - The step is idempotent and fails if a stale link would remain. Today's 44 were advanced with
       tools/evidence/advance-duplicate-links-2026-11-18.sql.
  2. **The 18 Nov prune** followed the standing workflow:
     - archive dump nizam_clean-20261118T111616Z.dump, copied with its sha256 to archives/prune-2026-11-18/ outside
       snapshot rotation;
     - an isolated proof on a restored copy: the source, evidence and release signature were unchanged and the audit
       passed;
     - the live prune: 2,631 retired revisions archived and removed, 1,634 kept because evidence names them;
     - VACUUM FULL: 6,028 → 4,881 MB.
     Afterwards: audit 41/41, 2,162 tests pass, 10,342 released.
  3. **Snapshot files outside the database** (E:\nizam-data\snapshots, 15.5 GB) are not deleted by the assistant;
     deletion waits for the owner. Safe to delete, about 11.7 GB:
     - the incomplete `.partial-*` dumps;
     - the retired `nizam` database's 3–6 Sep dumps and their empty pointer files;
     - the superseded 17 Nov dumps.
     The two Sept pre-prune archives that revision_archive_batch rows name stay.
- Where: tools/advance_duplicate_links.sql, tools/post_replay_sequence.sh (step 2-dup),
  tools/evidence/advance-duplicate-links-2026-11-18.sql, docs/CORPUS-STATE-2026-11-17.md.

### D-085 · 2026-11-18 · Page furniture batches: Sindh running heads and AJK folios, each law proven by its own tree
Area: L1 corpus · Status: standing (closes the D-083 measured-not-repaired item and the AJK folio item)
- Decision:
  1. **Sindh running heads.** tools/recrawl/sindh_title_patch.py, companion to the 15 Nov citation-line tool, reads
     the law's running head: its title, and the citation and folio lines printed with it. A top block is taken only
     when all of these hold:
     - it is on a page after the earliest one where its head line appears (the law's own heading is never touched);
     - its leading capital lines repeat at the head of two or more pages;
     - each of those lines is part of the law's recorded title (display, short or catalogue; "The" and the
       province's name folded).
     A loose first rule took a schedule's "TABLE-II" (doc 4698) and was replaced before anything was recorded.
     - Whole-head blocks are set aside, and head lines fused with law text are cut. There is one reading per page,
       with a 60-dpi render.
     - Generated: 223 laws and 1,915 pages.
  2. **AJK folios.** tools/recrawl/ajk_folio_patch.py sets aside a page number read into released AJK text ("any 202
     movable antiquity", doc 10935). A digits-only block at a page's head or foot qualifies only when its number
     minus its page is the law's folio offset, shared by at least three blocks.
     - Generated: 380 laws and 3,703 folios.
  3. **Every law proven by its own tree** (tools/recrawl/sindh_title_proof.py, on the release gate's dry-run tree
     dumps). A law passes only when:
     - no path is added or removed;
     - no kind, label, parent or heading changes;
     - every text change is a pure deletion of words its readings name as page furniture.
     Failing laws had this batch's readings retired unreplayed.
     - Sindh: 206 pass, 17 fail. Most failures would have regrouped sub-sections or clauses under a set-aside
       block, or deleted words outside the head ("Omitted.", "ORDINANCE NO. XII OF").
     - AJK: 374 pass, 6 fail (dry runs that failed or came out unchanged).
  4. **Applied:** about 1,750 Sindh page readings in 206 laws and about 3,100 AJK folio readings in 374 laws.
     - Both batches were held, replayed, re-verified and released again.
     - OCR-lane laws 4687 and 9664 were re-verified by verify_ocr and their holds lifted (the 15 Nov lift).
     - Doc 3330's run-only contents gap "45" kept its reviewed "found_elsewhere" decision, re-anchored to the
       active instrument (tools/evidence/reattach-toc-run-only-3330-2026-11-18.sql). The post-replay re-attach tool
       carries entry gaps only.
     - 10,342 released, none held.
- **Left, and why:**
  - The 17 Sindh and 6 AJK laws that failed the proof keep their furniture until each is read: a block that opens a
    provision or carries law words is not furniture.
  - Pages whose reading was refused for an ambiguous locator also keep theirs.
  - No Gilgit-Baltistan heritage law is held. None was found in the catalogue or in searches of the Assembly's
    legislation (18 Nov 2026), so there is nothing to land.
- Where: tools/recrawl/{sindh_title_patch.py, ajk_folio_patch.py, sindh_title_proof.py},
  tools/evidence/{sindh-titles-2026-11-18, ajk-folios-2026-11-18}/, tools/evidence/reattach-toc-run-only-3330-2026-11-18.sql.

### D-084 · 2026-11-18 · Embroidered patches in the layout's margins, and a stitched seam between pages
Area: client · Status: standing (supersedes D-082's whole-page cloth)
- Decision: the owner found the whole-page cloth too prominent and too basic. They asked for a few complex patches
  stitched at areas of the screen, a page transition related to embroidery, and nothing that overshadows text.
  - **The patches.** `EmbroideredPatch` is a round of cloth stitched onto the page, built in layers:
    - a woven ground: the cloth with warp and weft threads;
    - a merrow edge of dense satin over the rim, with its highlight;
    - a ring of tacking stitches;
    - a complex design per stitchwork:
      - phool: an eight-petal satin flower in two threads, ringed by twelve small flowers on a running-stitch vine
        with leaves, and French knots;
      - kashi: interlaced strapwork rings, a sixteen-point rosette, a satin eight-point star over a second star,
        petals and knots;
      - shisha: a herringbone ring, six mirrors in satin diamonds round a large mirror, and cross stitch;
    - a shadow, as if sewn on.
    It is stitched once into a cached image.
  - **Placement: in the layout, not the background.** Each patch sits beside a page's headline (`PatchedHeader`, the
    text kept clear of it) or in a card's empty corner. It scrolls with the page, so text never passes over it.
    - Discover: truck art beside the headline, blue pottery on the Constitution card's corner.
    - Library: blue pottery.
    - Heritage: the chosen region's craft, changing with the region.
  - **The transition.** Every route comes in through `StitchTransition`: the page fades up while a running-stitch
    thread is drawn across its top behind a moving needle, then fades (380 ms). It is off under reduced motion.
  - The satin hems, the stitch rule between Home's sections and the opaque tinted panels stand. Law pages carry no
    patch.
- Where: apps/mobile/lib/design/embroidery.dart (EmbroideredPatch, StitchTransition), design/components.dart
  (PatchedHeader), main.dart (routes), presentation/discover.dart, catalogue.dart, heritage.dart;
  test/heritage_test.dart (golden embroidery.png at 3x).

### D-083 · 2026-11-18 · AJK's inline headings and Sindh 1336's running heads repaired; a heading may close with ".-"
Area: L1 corpus · Status: standing (closes two of the D-080 "what remains" items)
- Decision:
  1. **`reviewed_heading_line` (agK3 rule C) is widened.** The printed heading may close with its terminator (".-",
     ".—", ".--", "-" or "—") before the text. The terminator is print furniture, as the parser drops it after any
     heading it splits itself, and the heading is the words before it. Readings that matched before are unchanged.
     tests/test_heading_line_terminator.py covers it.
  2. **AJK Antiquities Act 1986 (doc 10935)** prints every heading inline, bold and underlined ("5. Custody,
     preservation, etc. of certain antiquities.- (1) where ..."). It was held, pinned to `unreleased-v4` (whose
     split heads most sections) and replayed with page-read readings (patch-10935h.json, pages 4, 6, 9, 12, 13, 14
     and 18):
     - ss.4, 5, 6, 9, 20, 21, 25 and 36 by the widened heading-line rule. The v4 split stops at "etc." or at an
       amendment marker such as "4[Director General]", which is kept as printed.
     - ss.15 and 22 by their printed headings, whole, because v4's heading kept a line break.
     - Every section is now headed. Three false sub-sections opened mid-sentence at "sub-section (1)" are gone
       (187 → 184 provisions), and their words rejoin s.6(4), s.12(2) and s.16(2).
     - Owner delegation: decision-review-2026-11-18-delegated-10935 q1.
  3. **Sindh Cultural Heritage (Preservation) Act 1994 (doc 1336)** had its running-head title line read into ss.2,
     7, 9, 12 and 17. Following patch-1336r.json (pages 3–8):
     - where the line stands alone in its block it is set aside, and where it is fused with the law below it is cut,
       the law kept as printed;
     - s.22's margin-note block is set aside, and s.22 keeps the same words as its heading from the contents.
  4. Both laws were re-verified and released again (10,342). The post-replay sequence was run and the census
     recorded.
- **Measured, not repaired:** the same running-title leak across the Sindh Code. A first measure (a capitalised
  first line repeating at the head of two or more pages, read into provision text) finds 1,069 blocks in 321
  released Sindh documents: 366 fused with law text and 703 alone. The measure has not been checked against each
  law's own title, so it overstates. A corpus batch needs a title-exact rule and a tree diff per document (the
  15 Nov citation-line batch lost law text in nine documents until a diff caught it).
- Why: the owner asked for the D-080 remainders "AJK prints its headings inline" and "Sindh s.22's note and running
  heads" to be fixed.
- Where: nizam/corpus/segment.py (rule C), tests/test_heading_line_terminator.py,
  tools/evidence/heritage-2026-11-18/{build_d083_readings.py, patch-10935h.json, patch-1336r.json},
  tools/evidence/hold-d083-2026-11-18.sql, docs/SEGMENTATION-PROFILES.md.

---

## Open questions (not yet decided)

These were found and deliberately left open. Each will become an entry when it is decided.

- **Urdu and Roman Urdu precedent questions miss (D-133; D-137 measured the statute gloss here, no gain).**
  Recommendation: embed the judgment chunks in the 8B GPU space (D-099's route, which took statute Urdu r@50 to 1.0)
  and measure on dev.
- **Two different texts of one law, both served as current (found 24 Nov 2026, D-135).** 16 laws are reprinted
  inside multi-law documents (4497, 3949, 3696, 3553, 9283) with text that differs from their single-law twin
  (similarity 0.44–0.98). These are consolidations of different dates, and neither copy is marked historical. A
  reader can be shown the older text as current. Recommendation: a version-modelling slice. Read each pair's latest
  amendment, keep the newer as current and serve the older as a dated historical version (0096–0099 practice). The
  one identical pair (3389/2985) is then linked by a withdrawal writer for released copies, which needs a lead
  decision.

- **Party names as a search key in judgments of no sensitive category (found 24 Nov 2026, D-131).** D-122 says party names are
  not a search key. D-131 enforces it only where names are withheld. Recommendation: at search time, drop a hit whose only
  match with the query is its parties line, for every judgment, and measure what it costs dev recall first.
- **Fusion with the 8B space (D-099)** — decided for the GPU profile by D-101: its reranker reads citations then
  dense, without the BM25 windows. The CPU profile keeps the hybrid.
- **ADR-1d for the 8B space (D-112: not measured, low risk).** Dense-only, its sign bits cost nothing (bits4096 r50
  .968 against full .940), and the served path re-ranks the Hamming window against halfvecs at precision. A check
  after the cross-encoder needs a float re-embedding of the corpus, about 11 GPU-hours.
- **The degraded-mode gate (D-101, docs/04 §9.2)** — decided by D-106. On 305 dev cases the fused order reaches the
  0.90 fallback at 10.4% coverage, and test passed 18 of 18. An `unreranked` result now answers its clearest questions
  under its own threshold.
- **The CPU gate is under its precision target on test (D-102, D-106).** D-102: .833 [.608, .942] on 18 passes. After
  the refit on 305 dev cases (D-106): .909 [.804, .961] on 55, an interval that now contains 0.95 but a point
  estimate still under it. Recommendation (owner delegation): change nothing on the strength of test. Treat
  CPU-profile answers as the lower tier the UI marks. The remedies are annotated gold (stages A1/A2) and a faster CPU
  host with bge-v2-m3 (D-101).
- **Definition and cross-reference generators (docs/04 §4), held (20 Nov 2026).** Two of docs/04's four candidate
  generators are not built.
  - **Definitions** belong to context assembly (docs/04 §7: a passing unit's definitions, qualifications and
    dependencies are attached to the bundle). As candidates they would add no gold necessary unit, since the gold's
    necessary units are operative sections, and would crowd the bundle. Recommendation: build them in assembly, the
    next L3 component.
  - **Cross-reference expansion** ("s.302 → s.299") needs a refers-to edge that `legal_edge` does not yet hold (it
    has amends, repeals and empowers). Recommendation: an L2 slice extracting section cross-references, then the
    generator, measured on dev recall.
- **Is the Punjab Labour Code 2026 in force? (found 20 Nov 2026, D-104).** Section 435 repeals about 26 Punjab
  labour laws, among them:
  - the Punjab Minimum Wages Act 2019, Maternity Benefit Ordinance 1958, Payment of Wages Act 1936, Shops and
    Establishments Ordinance 1969 and Factories Act 1934;
  - the Bonded Labour System (Abolition) Act 1992;
  - the Punjab child-labour, domestic-worker and industrial-relations Acts.

  But s.1 brings the Code into force only "on such date as the Government may, by notification … specify". The
  corpus now serves both the Code (presumed in force) and the laws it repeals (the repeal is recorded undated). That
  is contradictory, and golden set 4 relies on three of the repealed laws (S4-C01, C03, C07, C08, U01, U03).
  - Evidence found: The Nation (29 May 2026) and ProPakistani (30 May 2026) report the Code enforced across Punjab
    after gazette publication. Neither gives the notification's number or date, and two legal commentaries say no
    commencement notification was verified.
  - **Searched further on 20 Nov 2026** (owner: "go ahead u go and get it"). The project's legal-source scout checked
    the Labour Department site, the Punjab Code and Punjab Laws portals (both timed out), the Assembly site, and
    English and Urdu sources, and found no commencement notification. The news items reuse the Act's own February
    enactment wording ("approval by the Governor and publication in the gazette").
  - **The strongest official evidence found points the other way.** Punjab Gazette (Extraordinary), 11 June 2026,
    Notification No. 129 of 2026 (p. 6653), publishes Labour Department Notification No. SO(L&P) 11-28/2023 of
    8 June 2026. In it the Governor makes the Punjab Restriction on Employment of Children Rules 2026 "in exercise of
    the powers conferred under section 21 of the Punjab Restriction on Employment of Children Act 2016", and defines
    "certifying surgeon" under the Factories Act, 1934. Section 435 of the Code repeals both Acts. The Government was
    making rules under them ten days after the news reports, so the Code had not commenced by 8 June 2026 on the
    Government's own record.
    - Source: labour.punjab.gov.pk/acts, "Punjab Restriction on Employment of Children Rules 2026.pdf", a 19-page
      scan read page by page.
    - Kept at E:\nizam-data\sources\punjab-labour-code-check\ (rules-2026.pdf sha256 af29c322…; the Department's
      copy of the Code, code-2026-dept.pdf, sha256 15d4bbb7…).
  - **Decision (owner delegation, the recommended option): the corpus is unchanged.**
    - The old Punjab labour laws stay served, consistent with the June 2026 gazette.
    - The s.435 repeals stay undated.
    - The Code keeps the owner's presumption of force. The presumption does not override evidence, and the evidence
      speaks only to 8 June, not to today.
    - Set 4's labour cases stand. The 2026 Rules are not landed: a scan (OCR by owner rule) and a new source (D-100).
  - Still recommended: obtain any commencement notification issued after June 2026 (Law and Parliamentary Affairs
    Department, Legis branch, which forwards Gazette notifications to the Labour Department) before changing the
    corpus. Then date the s.435 repeals from it with
    `tools/record_statutory_repeals.py` and `refresh_serving`, and move set 4's labour cases to the Code's
    provisions as a reviewed gold change. Until then, author no Punjab labour cases (sets 5–10 have none).
- **docs/10's abstention targets (D-102, D-106).** The stratum is 50 cases since D-104 (29 dev, 21 test), and records
  and statistics questions are vetoed since D-106. On test, recall is met in every mode (GPU .952). Strict abstention
  precision is not (GPU .690): 7 of the GPU's 29 abstentions decline an answerable question whose bundle was
  sufficient. Still unbuilt: requests for a predicted outcome or a guarantee, L6's professional-review outcome
  (docs/07; S4-X05 is the GPU's only unanswerable miss).
- **Corpus defects found by evidence assembly (D-107).** Each needs a page-read repair, law by law:
  - **The Constitution's Chapter 3A** (Federal Shariat Court, Arts. 203A–203J) is not a node: it sits inside Chapter 3
    (High Courts). The chapter-order rule keeps Art. 203B's definitions off Arts. 192–203. The tree is still wrong.
  - **Merged definition nodes.** Two or more clauses sit in one node (Companies Act 2017 s.2(17)–(18), PECA
    s.2(1)(xxiv)–(xxvi), Land Acquisition Act s.3(c)–(d), and others). The definition is served, but its citation
    names the first clause.
  - **Flattened sub-items:** a definition's (i), (ii) stored as its siblings. Assembly reads them back (the
    continuation rule); the segmenter should nest them.
  - **Footnotes and Gazette page furniture inside clause text:** MFLO s.7 Explanation; the Electoral Rolls Rules
    1957, where a page number was read as a label.
  - **A contents list stored as a section's text:** West Pakistan Money-Lenders Ordinance 1960 s.19.
- **Assembly latency (D-107, D-108).** After D-108: p50 about 150 ms and p95 about 240 ms on GPU bundles, against
  docs/04 §9's ≤ 25 ms for validate, assemble and gate. The rest is row fetching on this laptop. It must be measured
  on the serving host before any further rework.
- **Assembly not built (D-107, D-108, D-110):**
  - retrieval per sub-question (D-110 judges coverage per sub-question, but searches once);
  - the General Clauses Acts of Sindh, Balochistan, AJK and GB (not held);
  - matched-span offsets;
  - Urdu-script definitions.
- **A bundle unit crowded out by earlier units' additions (D-108, test S9-U05).** Holding room for every gated unit
  was measured and rejected (D-110). Any further variant needs fresh cases: the test split is spent for assembly.
- **Footnote false sections, the remaining queue (D-110):**
  - 6625: false rules likely, because its notes print in the rules' own "N." style;
  - 3712: the print typesets a note as a section;
  - 7416, 8481, 9315: OCR label misreads;
  - other pages' notes inside the text of 1992, 2840, 3717, 3958 and 4301.

  D-110 gives the detection query.
- **A coverage verdict per sub-question (D-110).** Sub-questions are split and traced, but word overlap was wrong on
  both real dev cases, so no verdict is drawn. A verdict needs:
  - a calibrated judge, for example the cross-encoder scoring each sub-question against the admitted units;
  - multi-issue gold to fit it on. Only 3 of 305 dev cases ask more than one question, so the next golden batch
    should hold multi-issue questions.
- **8B reranker serving latency (D-101, D-106).** A Kaggle T4 proxy (fp16, micro-batched) measured p50 4.5 s for 10
  passages and 24.5 s for 50: far outside budget. It needs an L4/A10-class GPU host with TEI or vLLM batching
  measured before the GPU profile is called within budget.
- **The CPU reranker on a faster host (D-101).** On this 6-core laptop only int8 mMiniLM at 800 characters × 10 fits
  1 s (+5.8 dev, +7.3 test). bge-v2-m3 gained +14.6 on dev but took 35 s for 50 passages. A production CPU host
  should be measured with `evals/rerank_budget.py` before its configuration is chosen. Fine-tuning the small model
  (ADR-2) waits for annotated labels.

- **The AJK Interim Constitution Act, 1974 (D-096).** Acquired, digest-verified and staged; no OCR needed for the law.
  The preflight predicts 33 unsettled repeated-label units, so it waits for its structure to be read before it is
  landed released. Its 7 amendment Acts are released and carry no `amends` edges to it until then.
- **Page furniture, the residue of D-089 (14 pages in 7 laws).** 1245 pp3–4, 2206 p3, 2505 p4, 2765 pp4–6, 2902 pp3–5,
  3919 pp5–6, 3992 pp33, 35. Removing each head changes the reviewed structure through a mechanism other than
  sentence continuation (in 1245 the folio text read into s.3(2) kept '(4)' a sub-section). Each page needs reading.
  The furniture of 1101, 1977 and 2904 waits on their drift regressions (next item).
- **Rebuild regressions found by the D-091 review (12 laws).** Today's segmenter rebuilds these worse than their
  release, and an approved replay is now refused until each is fixed: wrapped amendment headings (1101, 1977), a
  footnote taken for s.1's heading (2904), item 14 folded into 13 (2491), lost Parts (8213, 9310, 9659), a lifted
  clause (5494), a renumbered duplicate suffix (8173), 'Part I' read as '1' (4347 e3), damaged Gazette text (6576,
  6784). tools/evidence/drift-review-2026-11-18.json has each finding.
- **Preamble ordinals, the remainder (38).** After D-068 and D-072, 38 released laws still number a "preamble"
  after sections printed below it. The law page lists the preamble first regardless (D-065). They fall into four
  groups:
  - **Gazette laws whose rebuild failed the D-072 proof:** 5201, 5334, 5415, 5840, 6218, 9440.
  - **Older drift:** 5494, 6576, 6784, 8213, 9310, 9659.
  - **Gazette heads in forms the rule does not take** (scan noise, provincial gazettes): 6646, 6840, 7282, 8170,
    8214, 8345, 9067, 9219, 9435, 8602, 9285.
  - **Not an order problem: the "preamble" is the wrong text.**
    - Another law bound into the same file: 5409, 5673, 6923, 9623 (and 7318, the Estacode compilation).
    - A form's or a clause's recital: 7036, 9638, 9881.
    - A scan whose cover or contents pages were read as sections: 4635, 7411, 7434, 9214, 9254, 9315, 9832.
  - Each group needs page reading, law by law.
- **155 Gazette laws not replayed under D-072.** Their false Gazette Parts stand until a page-read repair, law by law.
- **The section list's frame-time tail** (8–13 of about 790 frames over budget on the emulator) and cold start need
  measuring on a phone. On 18 Nov the emulator itself degraded (D-070), so its raster numbers no longer judge the app.
- **ADR-1d for bge-m3: re-run if the CPU reranker reads deeper (D-112).** After reranking, binary costs +0.6 NDCG@10
  [−1.7, +2.9], so it stays. Dense-only it costs 4.7 recall@50 points, so a reranker that reads more than 10 units
  makes the window's recall matter more.
- **Retrieval p95 over ~1 s (D-098).** Hybrid p95 is 1.0–1.5 s on this host; the INV-5 gate (~350 ms p50) and the
  lexical windows dominate, and they predate the dense slice. The query encoder's 57 ms is over docs/04's 20 ms
  budget, mostly hidden by running the generators in parallel.
- **Roman Urdu retrieval** was 0 on dev (5 cases) for every generator (D-098). The GPU path reads it (D-099), and the
  alias index lifts the CPU path to r@50 .50 on dev and .46 on test (D-105). docs/04's full transliteration step and
  its 400–600 concepts are not built.
- **Deferred sources, to decide when retrieval is finished (D-100; docs/DEFERRED-SOURCES.md).** Each becomes an entry
  when decided:
  1. **FBR codes:** land the dated consolidations of the federal tax laws, and the 34 new laws? This first needs a
     rule for turning a whole-law snapshot into provision versions.
  2. **FBR Customs SROs:** land the 89 SROs, as `amends` edges to the Customs Rules?
  3. **SECP:** land the binding categories (Acts, Rules, Regulations, SRO notifications)? And do the 214 circulars,
     guidelines and directives belong at all?
  4. **PSX:** do the exchange rule books belong?
  5. **GB:** land the 2 new text laws from `GB_code.zip`, and OCR its 16 scans?
  6. **OCR:** run the OCR lane on the 874 AJK and 151 GB scans?
  7. **Judgments:** when to build the judgment pipeline for about 69,000 SCP, LHC, PHC and SHC judgments?
  8. **Acquisition exceptions:** re-check the remaining 40 against the new drops and Internet Archive?
