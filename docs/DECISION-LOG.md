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
Area: owner ruling · Status: standing
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
