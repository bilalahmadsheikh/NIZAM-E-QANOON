# The database as it exists

Dumped from the running cluster, not from the migrations. Everything below was
read out of `pg_catalog` — if a column is here, it is in the database.

PostgreSQL 17.11 (ParadeDB image) · schema `public` · 53 tables, 54 views, 4
materialized views · 103 migrations (through 0103) · 4.8 GB on disk, measured
17 Nov 2026 after prune batch 6 and `VACUUM FULL`. Application reads of law go through `operative_provision` alone
(see "Where a law runs" and "How far back the held text is the law" below).

```
btree_gist 1.7   ltree 1.3   pg_search 0.25.6   pg_trgm 1.6   vector 0.8.4   pgcrypto
```

---

## The shape of it

The corpus is a **ladder**, and each rung is a different kind of identity
(doc 02 §7). A rung never reaches past the one below it.

```
source_observation   what a portal exposed, when          — observation identity
        │ sha256
        ▼
     blob            bytes                                 — byte identity (SHA-256)
        │ sha256
        ▼
   document ──── page ──── text_block                      — an extraction of those bytes
        │                        │
        │ document_id            │ block_id
        ▼                        │
  instrument                     │                         — the legal work
        │ instrument_id          │
        ▼                        │
   provision ◄──────────────── provision_block             — INV-4: the citable unit
        │ provision_id                                       (every block has a home)
        ▼
provision_version                                          — INV-5: law as at a date
```

One `source_observation` can now produce several `instrument` expressions. Each
is tied to an ordinal and immutable source-block interval by
`instrument_expression_manifest`; the PDF and extracted blocks are stored once.

Evidence tables sit beside the ladder and record what happened rather than only
the current result: `acquisition_attempt`, `extraction_attempt`,
`extraction_verification`, `extraction_assertion`, `page_ocr_candidate`,
`segmentation_run`, `instrument_toc_entry`, `segmentation_curation_patch`,
`segmentation_profile_pin`, `segmentation_structural_candidate`, `segmentation_structural_adjudication`,
`segmentation_boundary_candidate`, `segmentation_boundary_adjudication`, and
`instrument_expression_manifest`.
Neither source observations nor these ledgers are silently pruned — C7 in
[CORPUS-CRITERIA](CORPUS-CRITERIA.md) says a failure that leaves no row is a
failure that cannot be found.

Extraction and segmentation are revision chains. Exactly one `document` is
active per `(sha256, language, publication_role)`. Exactly one `instrument` is
active per `(source_observation_id, expression_ordinal)`, while exactly one
`block_assignment_set` accounts for the observation's blocks. Superseded
derived revisions remain queryable until a restore-tested archive manifest
authorises their targeted pruning; source blobs, observations and extracted
blocks are not part of that pruning scope.

---

## Tables

### `source_observation` — what a portal exposed at a point in time

Observation key, not legal identity. The same Act fetched twice is two rows.

| column | type | note |
|---|---|---|
| `id` | bigint | identity |
| `source_id` | text NOT NULL | which scraper |
| `canonical_url`, `referring_url` | text | |
| `discovered_at`, `fetched_at`, `ingested_at` | timestamptz | **`fetched_at` is the corpus clock** — see A7 |
| `http_status`, `etag`, `last_modified`, `media_type`, `byte_length` | | what the server said |
| `sha256` | char(64) | byte identity; NULL if nothing landed |
| `object_key` | text | `raw/{source_id}/{sha256}`, never overwritten |
| `outcome` | `observation_outcome` | landed · failed · missing · skipped · unknown |
| `error_code`, `scraper_version`, `source_metadata` | | |

`UNIQUE (source_id, canonical_url, fetched_at, sha256) NULLS NOT DISTINCT`.
A `CHECK` requires a landed observation to carry both a `sha256` and an `object_key`.

### `blob` — bytes

| column | type |
|---|---|
| `sha256` | char(64) **PK**, `CHECK ~ '^[0-9a-f]{64}$'` |
| `object_key`, `source_id`, `media_type` | text NOT NULL |
| `byte_length` | bigint NOT NULL, `> 0` |
| `first_seen`, `created_at` | timestamptz |

One row per distinct file. The federal corpus has 1,030 paths and 982 blobs — the
difference is the same statute published twice, collapsed here where it should be.

### `document` — an extraction of those bytes

Doc 02 §7: identity is *blob + language + publication role + extractor*, so
re-extracting with a better parser produces a new document, not a mutation.

| column | type | note |
|---|---|---|
| `id` | bigint | identity |
| `sha256` | char(64) | → `blob` |
| `lane` | `extraction_lane` | E1 html · E2 born-digital · E3 mixed · E4 OCR · E5 image tables |
| `extractor`, `extractor_config` | text, jsonb | what produced it |
| `page_count`, `char_count`, `empty_pages` | | `page_count > 0` |
| `printable_ratio` | numeric(6,4) | 0–1 |
| `language` | text | en · ur · sd · mixed |
| `publication_role` | text | code_portal · gazette · other |
| `pdf_metadata`, `extracted_at` | jsonb, timestamptz | |
| `is_active`, `retired_at` | boolean, timestamptz | active revision selector |
| `supersedes_document_id` | bigint | → prior `document`, append-only revision chain |
| `verification_state` | text | unverified · passed · review · rejected |

Partial uniqueness: `UNIQUE (sha256, language, publication_role) WHERE is_active`.

### `page` and `text_block` — the printed page

`page` is keyed `(document_id, page_no)` and carries `lane`, `char_count`, `width`,
`height`. A page holding its *own* lane is what lets one PDF be part born-digital
and part scanned without rejecting the whole file.

`text_block` is the atom of extraction:

| column | type | note |
|---|---|---|
| `id` | bigint | identity |
| `document_id`, `page_no` | | → `page` ON DELETE CASCADE |
| `block_no` | int | order within the page |
| `reading_order` | int | **`UNIQUE (document_id, reading_order)`** — dense and monotonic (S4) |
| `x0 y0 x1 y1` | numeric(9,3) | coordinates are evidence, not truth (doc 02 §5.1) |
| `text` | text NOT NULL | |
| `script` | text | |
| `confidence` | numeric(4,3) | NULL for clean text, set for OCR (A8) |

### `instrument` — the legal work

| column | type | note |
|---|---|---|
| `id` | uuid | |
| `document_id` | bigint | → `document`; reviewed expressions may share one source document |
| `jurisdiction` | `jurisdiction` | fed · punjab · sindh · kp · balochistan · ict · ajk · gb |
| `kind` | `instrument_kind` | constitution · act · ordinance · order · regulation · rules · sro · notification |
| `number`, `year` | text, smallint | year 1800–2100; NULL only for an owner-declared undated instrument (0063), rendered `undated`, never inferred |
| `short_title`, `long_title`, `preamble` | text | |
| `enacted_on`, `commenced_on`, `repealed_on` | date | |
| `status` | `lifecycle_state` | in_force · repealed · spent · lapsed · not_yet_commenced |
| `repealed_by_id` | uuid | → `instrument` |
| `duplicate_of` | uuid | → `instrument`; NULL means *not yet assessed*, **not** "not a duplicate". Set by exact-tree identity (0036), partial-copy supersession (0054), same-text copies (0062), or reviewed expression source variants (manifest method `nizam.expression_source_variant/1`). The latter means issued identity only, not text equality; ordinary replay is refused. See `docs/EXPRESSION-SOURCE-VARIANTS.md`. |
| `gazette_ref`, `source_url`, `source_sha256`, `scope`, `extraction_conf`, `published` | | |
| `source_observation_id` | bigint | → the official portal observation interpreted by this revision |
| `expression_ordinal`, `expression_role` | smallint, text | stable expression number; `primary` or `embedded` |
| `source_start_block_id`, `source_end_block_id` | bigint | inclusive source span, guarded to this document and reading order |
| `is_active`, `retired_at` | boolean, timestamptz | active revision selector |
| `supersedes_instrument_id` | uuid | → prior `instrument`, append-only revision chain |
| `verification_state` | text | unverified · passed · review · rejected |
| `display_title` | text | the name to render (INV-1); NULL renders `short_title`. Derived from `instrument_metadata_assertion` (0070) |
| `text_language` | text | `en` · `ur` · `sd`: the language of this expression's released text, **measured** from it (0070). Not docs/03b's authentic language |

`CHECK ck_repeal`: `status = 'repealed'` **iff** `repealed_on IS NOT NULL`.

`number`, `enacted_on`, `commenced_on`, `display_title` and `text_language` are
derived after every replay from `v_instrument_metadata_current` by
`tools/apply_instrument_metadata.py` (post-replay step 2b4; audit A15). `number`
is fill-only: a number the segmenter read is kept, and a disagreement is reported.
`short_title` is never changed, because replay matching and identity key on it.

Active expression identity is unique on
`(source_observation_id, expression_ordinal)`. Citation lookup remains a
*non-unique* index. Post-18th-Amendment, one Act legitimately
appears on both a federal and a provincial portal (doc 03b §3), so the duplicate
question is answered by `duplicate_of` rather than forbidden by a constraint.

### `instrument_expression_manifest` — reviewed boundaries inside a PDF

This append-only table separates source-document identity from legal-expression
identity. Its key fields are the source observation and document, expression
ordinal/role, inclusive start/end block IDs, detected title/kind/year/number,
review basis, method and JSON evidence. `materialized_instrument_id` identifies
the derived tree when retained. Retired manifests remain source evidence even
after a restore-tested prune removes their superseded derived tree.

The active partial unique index permits one current manifest per
`(source_observation_id, expression_ordinal)`. A trigger proves observation SHA,
document SHA and both blocks agree and that the span follows reading order.

**Undated expressions (0063).** `detected_year` and `instrument.year` may be
NULL, but only on the owner's word. A manifest may carry `detected_year` NULL
only when its evidence has `year_status` = `undated` and `year_owner_decision`
{`export`, `document_id` = the manifest's document, `question_id`, `choice` =
`undated`} (CHECK `instrument_expression_manifest_undated_by_owner`).

An active instrument may carry `year` NULL only while an active manifest for
its `(source_observation_id, expression_ordinal)` has `detected_year` NULL.
This is a deferred constraint trigger, `instrument_undated_guard`, checked at
commit because the materialiser inserts the instrument before its manifest. It
also fires when an instrument's `is_active`, `source_observation_id` or
`expression_ordinal` changes. A plain single-expression build therefore cannot
store a NULL year.

Two deferred guards on the manifest cover the other direction:

- `manifest_undated_retirement_guard`: retiring, re-dating or deleting an
  undated manifest is refused if it leaves an active NULL-year instrument with
  no active undated manifest. A re-materialisation, which retires the old
  manifest and inserts its successor in one transaction, passes.
- `manifest_undated_instrument_guard`: an undated manifest that names its
  `materialized_instrument_id` must name a NULL-year instrument.

An audit criterion has been drafted for review (A12, not yet in
`tools/audit/criteria.sql`). It reports the number of undated instruments and
fails on any undated instrument without the owner's undated manifest.

The path prefix of such an instrument reads `yundated`; clients show
`undated`, and the preview API returns `year_display`. No year is ever
inferred (INV-1). `v_instrument_duplicates` leaves undated instruments out,
because two NULL years are not one citation. First case: doc 1973's three
West Pakistan notifications (export i, 1973 q3).

Builder side (as built 10 Oct). A reviewed plan expression states `"year":
null` only with `"year_status": "undated"` and an `owner_decision`
{`export`, `document_id`, `question_id`} whose export answer has a choice in
the closed set {`undated`}. `validate_plan` in
`tools/materialize_multi_instrument.py` checks this with
`owner_decision_answer`, and it refuses `year_status` on a dated expression and
a `title_correction` on an undated one. The materializer writes the manifest
evidence `year_status` and `year_owner_decision`, the citation plus `choice`,
and refuses to write it if the build produced a year. `build()` in
`nizam/workers/segment.py` takes a reviewed identity whole: it infers no kind,
year or number beside it, so an undated title such as '... Opium Act, 1878 ...'
cannot lend its year. The legacy listed documents (PRIMARY/COMPILATION) build
from their stored years, and a missing year is refused there rather than filled
from the catalogue's year.
Current state: 131 active manifests across 11 official observations and 11
retired predecessor manifests.

**Historical expressions (0064).** Three nullable columns let an expression be
released as a dated historical text, never as current law, on the owner's
word:

| column | type | note |
|---|---|---|
| `historical_validity` | daterange | NULL = current consolidated text. Otherwise the reviewed window `[from, to)` in which this text was the law |
| `current_source_observation_id` | bigint | → `source_observation`; with the ordinal, the **stable key** of the current expression of the same work |
| `current_expression_ordinal` | smallint | ≥ 0 |

CHECK `instrument_expression_manifest_historical_shape`: all three NULL, or a
non-empty window bounded on both sides, a target that is not the manifest's own
`(source_observation_id, expression_ordinal)`, an `evidence.historical_basis`
object (the source of each bound), and `evidence.historical_owner_decision`
{`export`, `document_id` = the manifest's document, `question_id`, `choice` =
`historical-expression`}. The target is a key, not `instrument(id)`: a revision
id is retired by every replay of the current expression and an FK would block
restore-proof pruning. No FK is possible on the pair; `validate_plan` and A13
check that it resolves.

Three deferred constraint triggers, checked at commit because the materialiser
writes instruments and versions before the manifest:

- `manifest_historical_versions_guard` and `instrument_historical_versions_guard`
  (one function, `check_historical_versions()`, on both tables): while an
  active manifest gives `(observation, ordinal)` a window, every version of
  every active instrument of that key satisfies `validity <@
  historical_validity`. An open-ended version never does. The instrument-side
  trigger exists because an exact-tree overlay copies the instrument row and
  never touches the manifest.
- `manifest_historical_retention_guard` (`check_historical_retention()`):
  retiring, un-windowing or deleting a historical manifest is refused while an
  active instrument of its key is left with no active historical manifest. A
  replay that retires the manifest and inserts a windowed successor passes. The
  only other way out is an explicit withdrawal: a successor manifest with no
  window whose `evidence.historical_withdrawal` {`withdraws_manifest_id`,
  `reason`, `owner_decision`} names a historical manifest of the same key
  (CHECK `instrument_expression_manifest_historical_withdrawal_shape`). It is
  written only by a migration, never by a replay.

`v_instrument_historical` lists each active instrument that an active manifest
declares historical, joined on `(source_observation_id, expression_ordinal)`
and `i.is_active`, never on `materialized_instrument_id` (an overlay leaves that
pointing at the copied-from revision). It exposes `valid_from`, `valid_to`, the
current-expression key, `historical_basis` and `historical_owner_decision`.
`v_release_instrument` is not redefined: it stays the release proof. The gate
is applied by the reader. `nizam/storage/library_read.py` lists and opens a
historical instrument only for an `as_of` inside its window. `children()` and
`provision()` inherit the gate. The preview API carries `historical`,
`valid_from`, `valid_to` and, on single opens, the resolved
`current_instrument_id`. Without an `as_of` the API asks for today, so a
historical text is not discoverable by default; this is deliberate.

Builder side (as built 13 Oct). A plan expression carries `version_validity`
{`from`, `to`, `owner_decision`, `historical_basis`} and `current_expression`
{`document_id`, `expression_ordinal`}, both or neither. `validate_plan` checks
the owner's answer with `owner_decision_answer` (closed set
{`historical-expression`}), `from < to <= today`, a non-empty basis, and that
the target resolves to exactly one active canonical non-historical instrument.
That instrument must not be this expression, and its earliest version must open
at or after `to`. `--apply` refuses a basis that still carries `pending_owner`.
`SegmentedInstrument.version_validity` carries the window to
`nizam.storage.legal_write`, whose one `VERSION_INSERT_SQL` writes
`daterange(from, to, '[)')` for both writers. `save()` refuses a window, and
refuses to replace an expression whose active manifest is historical.
`save_many()` requires each manifest and instrument to agree, and refuses a
replay that drops a window without an explicit withdrawal. The legacy listed
path (`prepare()`) carries an active window forward onto the rebuilt
expression of the same ordinal and first block, or refuses. First case: doc
4434 e0 (export k, 4434 q3), the Constitution as amended to the Twenty-second
Amendment Act, 2016. Its current expression is doc 4419 e0 (observation 507).
Its window is `[2016-06-08, 2017-01-07)`, with the upper bound pending the
owner's choice between the deeming date and the 30 March 2017 enactment.

### `provision` — INV-4, the citable unit

| column | type | note |
|---|---|---|
| `id` | uuid | |
| `instrument_id` | uuid | → `instrument` CASCADE |
| `parent_id` | uuid | → `provision` CASCADE, `CHECK parent_id <> id` |
| `kind` | `provision_kind` | part · chapter · section · article · subsection · clause · proviso · explanation · illustration · schedule · preamble · form · appendix · annexure · order · notification (0117, D-115: an unnumbered notification as one unit, label "Notification") |
| `label`, `heading`, `marginal_note` | text | `label` is what a lawyer cites |
| `ordinal` | int | document order |
| `path` | **ltree, UNIQUE** | lineage; subtree queries with `@>` / `<@`, no recursive CTE |
| `is_active`, `retired_at` | boolean, timestamptz | current derived node versus retained revision history |
| `first_block` | bigint | → `text_block`, the evidence anchor (A3) |
| `first_page`, `last_page` | int | must fall inside the document (A4) |

Identity is *structural* — instrument plus position — so re-chunking for retrieval
can never invalidate a stored citation. That is the whole point of INV-4.

**Unnumbered provisions** (owner decision 6 Oct 2026, doc 128). Some instruments
print an operative provision with no number, such as doc 128's Act-level
"Repeal: ... are hereby repealed." after its Schedule. It is stored with no new
column and no new kind. It is a `section` (an Act-level operative unit, so it
stays in the operative views), its `label` is the printed lead word (`Repeal`),
and its `heading` is the same word. A label with no numeral in a numbered kind
(`section`, `article`, `subsection`) **is** the marker. Every active section,
article and subsection carried a numeral in some script when this was decided,
and `nizam.shared.corpus_types.is_unnumbered_provision(kind, label)` is the one
predicate for it. A citation renderer must ask that predicate before writing "section N". An
unnumbered provision is cited by its printed word, as the instrument's unnumbered
"Repeal" provision, never as "section Repeal". No number is invented (INV-1).
Only a reviewed opener under segmentation profile rule
`unnumbered_tail_provision` or `unnumbered_root_provision`
(docs/SEGMENTATION-PROFILES.md) produces one. Its ltree key is `…s_Repeal`.
Path segments are internal keys, not citations. One exception is not an
unnumbered provision: a paragraph printed without a number but numbered by
the owner's recorded decision (doc 268's 1998 Order para 1) is stored as
label `1`. Its opener cites the decision-review export, document and question
in the curation patch evidence.

**Order suffix** (owner decisions 6-7 Oct 2026, doc 999). Doc 999 prints two
sections numbered 2: "2. 1[Repealed] / Nothing herein contained ..." and then
"2. In this Act ..." (Interpretation clause). The owner kept both as citable
sections. Both keep the printed `label` `2`; nothing is renumbered and no
column is added. The later print's path ends in a print-order marker:
`…s_2` and `…s_2__o2`. `slug` never produces a double underscore, and no path
contained one when this was decided, so the marker cannot be mistaken for a
label. It depends only on print order among the same-label prints, not on the
child's position, so the key survives any change to other siblings (INV-4).
The citation of the later print is "s.2 (second)". A renderer must take the
suffix from the stored path through
`nizam.shared.corpus_types.order_suffix(path)` (`print_occurrence(path)` gives
the number) and append it wherever it writes the label. The suffix is never
generated and never counted from siblings at render time (INV-1). Only a
reviewed `source_order_suffix_labels` entry produces the marker: {kind, label,
source_block_ids in print order, owner_decision}, under segmentation profile
rule `order_suffix_label`. Since 8 Oct 2026 the kind may also be `subsection`
(doc 1034 s.5 prints sub-section (2) twice; owner decision 7 Oct q2
"keep-both"): the paths are `…s_5.ss_2` and `…s_5.ss_2__o2`, cited "s.5(2)" and
"s.5(2) (second)", by the same `order_suffix(path)`. The kind may also be
`clause` (owner decision 8 Oct, doc 1457 q4 "keep-both"). s.20 prints items
(i) and (ii) twice, and they are cited by order: `…s_20.cl_i__o2` is
"s.20(i) (second)". An order-suffix entry must cite an answer whose choice is
"keep-both". Audit S6 keys sibling labels by (kind, label,
marker), so a kept pair is one citation each and a stray duplicate still fails.

**Named schedule rows** (owner decisions 7 Oct 2026, docs 1078 and 1121). Both
copies print a ten-column recruitment table with no serial column; each row is
identified only by the post it fills ("Assistant Research Officer (G-17)",
"Cane Commissioner (BS-19)"). The owner ruled that each row is a citable
Schedule row identified by its printed post name and grade, with no number
supplied (export -e: 1078 q1 "schedule-rows-by-post", 1121 q2 "rows-by-post").
No column and no kind is added. Such a row is a `clause` under the schedule,
its `label` is the printed post cell verbatim except for the cell's closing
stop, which the label drops ('Superintendent' for the printed
'Superintendent .', doc 1106; lead decision 8 Oct, as printed numbers drop
theirs), and its text is the whole row line, post cell and stop included.
Under an open schedule group caption (below) the row is the caption's child. Its path ends in a marker: `…sch_SCHEDULE.cl_Cane_Commissioner_BS_19__nr`,
keyed by the full label slug (never cut at 40 characters), so two long post
names cannot fall back to a position suffix. A collision is refused. The label's
shape cannot carry the marker, since a grade carries digits and
`is_unnumbered_label` refuses it. A renderer must ask
`nizam.shared.corpus_types.is_named_schedule_row(path)` before writing a clause
label and cite such a row as the Schedule entry for the post: "Schedule, Cane
Commissioner (BS-19)", never "clause Cane Commissioner (BS-19)" and never a row
number (INV-1). Only a reviewed `source_named_schedule_rows` entry produces the
marker: {source_block_id, schedule_block_id, label, source_text,
owner_decision}, under segmentation profile rule `named_schedule_row`.

**Schedule group captions** (owner decision 7 Oct 2026, doc 1106 q3
"rows-by-group"; lead decision 8 Oct). Doc 1106's 1996 Schedule prints a wing
title ("GAZETTED STAFF OF FLORICULTURE WING") and group captions ("GREEN BELT
GROUP") across the table, and the post serials restart under each caption.
Each row is identified by its caption and its printed serial ("GREEN BELT
GROUP, 2"), or by its caption and post name where no serial is printed;
nothing is renumbered. There is no `group` kind, so a caption is stored as a
`part` under the schedule (a wing title, level 1) or under its wing (a group
caption, level 2), with `label` and `heading` the caption as printed. Its rows
are its children and keep their printed labels. The path ends in a marker:
`…sch_SCHEDULE.pt_GAZETTED_STAFF_OF_FLORICULTURE_WING__gc.pt_GREEN_BELT_GROUP__gc.cl_2`.
It is keyed by the full caption slug (never cut at 40 characters), and a
collision is refused. A renderer must ask
`nizam.shared.corpus_types.is_schedule_group_caption(path)` before writing a
part label and cite the caption exactly as printed, never as "Part GREEN BELT
GROUP" (INV-1). Only a reviewed `source_schedule_group_captions` entry
{source_block_id, caption, level 1|2, owner_decision} produces one, under
segmentation profile rule `schedule_group_caption`.

**Printed number markers** (owner decision 8 Oct 2026, doc 1225, export -f
q1 "contents"). The Sindh Finance Act, 2006 prints nine contents rows and eight
body sections. Contents row 3 is the margin note of the quoted Stamp Act s.29
that body s.2(ii) substitutes, so from body s.3 on the contents runs one ahead.
The owner chose the contents numbering: the quotation is cited s.3 of this Act,
and body ss.3-8 are cited 4-9. The stored `label` is the cited number, because
it is what a lawyer cites. The print is kept on the path, as the last thing on
the ltree label: `…s_4__p3` means the copy prints "3.", and `…s_3__pnone` means
the copy prints no number of this instrument there. `none` is used, not `0`,
because a printed "0" is a possible label and the rule refuses a printed label
"none". Printed labels are restricted to `[A-Za-z0-9]`, so the marker is the
print itself. No column is added, and no number is written into the text: s.3's
text is the quotation verbatim, opening '"29 - In the absence ...'. A renderer
must take the print from the stored path through
`nizam.shared.corpus_types.printed_label(path)`. That returns None for an
ordinary provision, '' for `__pnone`, and '3' for `__p3`. `printed_note(path)`
gives '(printed 3)' or '(no number printed)'. A renderer never derives the print
at render time and never counts it from siblings (INV-1). Only a reviewed
`source_owner_cited_labels` entry produces the marker: {kind section|article,
printed_label, or null with source_prefix, cited_label, source_block_id,
owner_decision}, under segmentation profile rule `owner_cited_label`. A print
that also carries an order suffix is refused. A **continuation** entry is also
possible (owner decision 8 Oct, doc 1457 q3 "open-at-p3"). In doc 1457, s.6
is opened by its owner-cited opener at p3's printed words
'6["(1) The Speaker ...', where the 6 is a footnote marker and the number
comes from contents row 6. The copy prints "6." only on p4, before
sub-section (2). An entry with `printed_label` equal to `cited_label` and
`continues_opened: true` names that later print. The print stays in s.6's text
and the rest of the unit is read inside s.6, so no second s.6 opens. Because
the number is printed in the source (p4 "6."), an opener with a used
continuation entry whose printed label equals the cited label carries no
printed-number marker. Its path is `…s_6` and the stored label is the print
(lead decision 8 Oct). An opener without such a continuation keeps `__pnone`,
as doc 1225's s.3 does. `__pnone` also covers a copy that prints no legible
number of this instrument. Doc 1463's KP copy of the Suits Valuation Act prints
s.11 as '2[1—(i) Notwithstanding ...' (owner decision 8 Oct, export -g q1
"release-as-is"). The section is opened as s.11 from its contents row and margin,
the corrupt print stays visible in its text, and the path is `…s_11__pnone`. An
owner-cited opener read while a top-level Part or Chapter is open belongs to
that division (`…pt_PART_HI.s_11__pnone`). An owner-opened unit printed again at the root without a
continuation entry is refused.

**Arabic-script labels on the path** (owner decision 18 Oct 2026, doc 4631 q1
"urdu-rule-openers"). An Urdu copy can print its rule numbers in Urdu digits,
for example "(۴)". A reviewed `source_printed_rule_openers` entry may carry such
a label, under segmentation profile rule `reviewed_urdu_numeral_opener`
(unreleased-v4, data-gated). In a parse that applies one, Arabic-script labels
get ASCII ltree keys. Digits are mapped to ASCII digits, so "۴" becomes `…s_4`
and a sub-rule "(۱)" becomes `…ss_1`. A letter is keyed by the last word of its
Unicode name, so form "ب" becomes `…form_beh` and "الف" becomes `…cl_alef_lam_feh`.
The stored `label` stays as printed. A renderer cites the stored label, never
the key (INV-1).

**Illegible print in provision text** (owner decision 18 Oct 2026, doc 4640 q6
"illegible-marker"). Where the source print is illegible and no owner
transcription exists, the provision text carries the literal marker
`[illegible]` at the hole. It is never reconstructed and never silently dropped.
Each occurrence is flagged in the reading that produced it and listed in the
plan's `source_anomalies`. This is the project convention for in-text illegible
print.

### `provision_ancestor` — disposable subtree acceleration

One row maps a descendant `provision_id` to itself or to one real ancestor
`provision.path`, with graph distance. The primary key
`(ancestor_path, provision_id)` makes a subtree an ordinary B-tree equality
lookup; `provision_ancestor_provision` supports retirement/cascade and upward
context assembly. It is derived from `provision.parent_id`, not source evidence.

Migration 0027 removed 1,563,444 rows for the synthetic
`jurisdiction.kind.year_number` path prefix. Those strings identify an
observation but are not provisions and could never be the root of a
provision-based subtree query. On 17 Nov 2026 the active closure is 3,242,502
rows covering all 1,197,584 active provisions; audit S9 recursively derives the
expected graph and requires zero missing, extra, or stale rows.

### `provision_block` — every block has a home

The table that makes "nothing is discarded" checkable. See
[CORPUS-CRITERIA C4/C5](CORPUS-CRITERIA.md).

| column | type |
|---|---|
| `assignment_set_id` | uuid | → `block_assignment_set`; part of the PK |
| `block_id` | bigint | → `text_block` CASCADE; part of the PK |
| `document_id` | bigint → `document` CASCADE |
| `provision_id` | uuid → `provision` CASCADE; NULL for non-body roles |
| `role` | `block_role` |
| `chars` | int |

```sql
CHECK (CASE
  WHEN role IN ('body','heading','schedule_row','preamble')
       THEN provision_id IS NOT NULL
  WHEN role IN ('contents','preface','running_header','unstructured','unassigned')
       THEN provision_id IS NULL
  ELSE true END)                                    -- 'footnote' may go either way
```

Partial indexes on `role = 'unassigned'` and `role = 'unstructured'` exist so the
two defect queries cost nothing.

The primary key is `(assignment_set_id, block_id)`. That distinction is
essential: re-segmentation can retain an older evidence mapping and append a new
mapping for the same immutable text block without double-populating the active
corpus. Consumers join through the one active `block_assignment_set`.

`unstructured` is for a document with text but no provision structure — a PDF
reading only "THIS LAW HAS BEEN REPEALED", recruitment rules published as a
ten-column table, or a source whose text layer cannot be read. Three distinct
PDFs (48 official observations), 665 assigned blocks. They are listed with their reasons in
`v_unstructured_document`. `unassigned` means something different and worse: the
document *was* segmented and a block was missed. That one must be 0.

### `provision_version` — INV-5, law as at a date

| column | type | note |
|---|---|---|
| `id` | uuid | |
| `provision_id` | uuid | → `provision` CASCADE |
| `validity` | **daterange NOT NULL** | when this text was the law |
| `text_normalised` | text NOT NULL | |
| `text_en`, `text_ur` | text | |
| `operation` | `version_op` | original · inserted · substituted · omitted · amended |
| `amended_by_id` | uuid | → `instrument` |
| `amendment_note`, `extraction_conf`, `verified_at`, `verified_by` | | |

```sql
EXCLUDE USING gist (provision_id WITH =, validity WITH &&)
```

Two versions of one provision cannot overlap in time. Not a convention, not a test —
the database refuses the write. A6 is enforced rather than measured.

Current text is written `daterange(<observation date>, NULL)`. A historical
expression (0064) is written `daterange(from, to, '[)')` inside its manifest's
window, so it never satisfies `@> current_date` (A7 sets it aside; A13 judges it).

### `extraction_attempt` and `segmentation_run` — the ledgers

`extraction_attempt`: `sha256`, `outcome` (extracted · rejected · error), `lane`,
`reason`, `detail` jsonb, `duration_ms`. A partial index on `outcome <> 'extracted'`
*is* the OCR backlog.

`segmentation_run`: `document_id`, `outcome`, `reason`, `segmenter`, `provisions`,
`sections`, `max_depth`, `body_starts_page`, and the acceptance test —
`toc_found`, `toc_entries`, `toc_matched`, `toc_missing`, `toc_extra`,
`toc_agreement numeric(6,4)`. Indexed on
`(outcome, toc_agreement) WHERE outcome <> 'segmented' OR toc_agreement < 0.95`,
which is the review queue, ranked worst first.

As built, 11 Oct. Every worker and materializer run writes two more keys into
`detail`: `segmenter_sha256` (the sha256 of `nizam/corpus/segment.py`) and
`profile`. A run that replaced a released tree although it changed also
writes `release_change_approval` and `release_change`. The guard behind this is
described in docs/SEGMENTATION-PROFILES.md, "Ungated changes and released
trees".

### `block_assignment_set` — immutable segmentation revisions

Groups one complete block ledger for one official observation. It records the
document, optional resulting instrument, segmenter version, `is_active`, and the
`supersedes_set_id` revision edge. Partial uniqueness permits exactly one active
set per observation. `provision_block` rows always belong to one set, so active
and historical mappings cannot be confused.

### `instrument_toc_entry` — the PDF's own structural oracle

Stores the printed entries in order without collapsing repeated labels. Each row
has the printed label/heading/page, its resolved provision when any, and both
`source_block_id` and one-based physical `source_page`. `v_toc` therefore links
back to the verbatim block, geometry and reading order and forward to the parsed
tree; `v_toc_gap` is the unresolved-entry worklist. Audit A9 rejects a missing or
cross-document/page source anchor.

`source_char_offset` (0051) indexes the anchoring block's VERBATIM text.
Correction as built, 11 Oct 2026, owner-approved:
`segment._toc_source_entries` had measured it in the curation-patched text. A
patch that changed a contents block's length shifted every later row (doc 4330:
'22-B' read as '22-B.', so 22 rows were one character late). A patch that moved
a row into another block anchored the row to a block that does not print it
(doc 2205: label 16 had offset 97 in a 54-character block, which tripped A9).

`segment._verbatim_toc_anchors` now maps each entry back to the verbatim text,
ungated by profile. Unchanged text keeps its offset, and an offset inside an
unchanged stretch maps exactly. An offset at the start of a rewritten stretch
maps to the verbatim start. A row moved in by a reading is found by its printed
start among the verbatim blocks of its page, and only a unique hit is used.
Anything else is stored as NULL ("not recorded"), never a guess. Provisions and
contents links do not change.

### `toc_gap_adjudication` — page-evidenced decisions on contents gaps

Migrations 0042, 0043, 0050, 0060. An append-only, supersedable decision for one
unresolved printed contents entry (`toc_entry_id`; NULL only for 0043's legacy
run-only gaps). `v_toc_gap_pending` holds every gap whose latest decision is
missing or `parser_defect`, and the release views block an instrument with any
such row. The resolutions, and what each must carry:

| resolution | means | evidence required |
|---|---|---|
| `parser_defect` | the law is in the PDF and the tree misses it; classifies, closes nothing | `defect_class` |
| `found_elsewhere` | the unit is a live provision of this instrument the linker did not pick | `found_provision_id` |
| `other_instrument` | the unit belongs to another instrument | `other_instrument_id` |
| `absent_in_source` | the official source does not print the unit (the Act lacks it) | human page review + render, or assistant page review + render + `render_sha256` + `observed` |
| `source_incomplete` | the Act has the unit; this landed copy does not print it | an exact `toc_entry_id`, `source_incompleteness_id`, and the same page-review evidence as `absent_in_source` |

**Carried by replay (as built 11 Oct; lead decision for doc 2205).** A replay
regenerates contents-entry ids, so a decision keyed to the old entry no longer
counts. That made the release-gate guard in `legal_write.save` refuse every
replay of a released instrument holding gap decisions.

`save()` now carries each standing decision of the replaced tree onto the new
entry in the same transaction, before the gate check, mirroring the S7 carry.
The carry needs an exact match: the same printed label, printed heading,
`entry_kind` and `source_page`, unresolved on both sides. The match must be
exactly one entry in the old tree and exactly one in the new. The target must
also be unchanged. A `found_elsewhere` is carried only when its provision has
exactly one counterpart with the same path, kind, label and first block. An
`other_instrument` is carried only when its instrument is still live. A
`source_incomplete` is carried only while its 0054 record still stands.

The source anchor (block, offset) is not part of the identity. The carry
appends a new row whose evidence holds `carried_by_replay` (old adjudication,
old and new instrument and entry ids). The old row is never edited. Anything
inexact, ambiguous or refused by a guard carries nothing, so the gate judges
the new tree as before. `tools/reattach_orphaned_toc_adjudications.py` treats
a carried decision as done.

`source_incomplete` (0060) is the "release with the gap recorded" path. Its
trigger admits it only while the named `source_incompleteness` row (0054) is
the latest for the instrument's own source observation, is about the same
document, and says `no_complete_copy_acquired`; where a complete copy is held
the truncated tree is retired instead (`tools/apply_source_incompleteness.py`).
No provision is created. `v_toc_gap_source_incomplete` lists the entries so
released, with the record they rest on and whether it is still current — render
them as "not available in this copy", never as repealed or absent. Record with
`tools/adjudicate_toc_from_source.py`, after the dated refetch
(`tools/record_source_refetch.py`, which writes `acquisition_attempt` with
`unchanged_copy` per 0055) and the 0054 row (a reviewed file in
`tools/evidence/`). `./nz toc-reattach` carries the decision across a replay
while its 0054 record stands.

### `toc_disposition_assertion` and `toc_disposition_withdrawal` — contents rows that print a repeal

Migrations 0045, 0046, 0052, 0061. A `toc_disposition_assertion` is the
rendered-source proof that a printed contents row denotes an omitted or
repealed section (`disposition` `omitted` | `repealed`). It is keyed to the
printed entry — observation, expression, `source_block_id`, `printed_label` —
not to the parser's ordinal, so it survives replays; its trigger requires an
exact live `instrument_toc_entry` and lets a superseding row correct only the
same printed entry. The segmenter reads `v_toc_disposition_assertion_latest`
(through `legal_write.toc_dispositions_for`) and materialises an empty
`operation='omitted'` version citing it in
`provision_version.source_toc_disposition_assertion_id`; an assertion it cannot
match raises, so a wrong one makes the document unreplayable.

`toc_disposition_withdrawal` (0061) says a recorded disposition no longer
applies, without editing it: one row per assertion (`assertion_id` UNIQUE),
with `reason`, `owner_decision` {`export`, `document_id`, `question_id`,
`choice`} citing a decision-review answer, `evidence` (at least the export's and
the answered card's SHA-256), `withdrawn_by`, `withdrawn_at`. UPDATE, DELETE and
TRUNCATE are refused. Its trigger admits only the governing (latest) assertion
of its printed entry, only for a document that observation was built into, and
only while no instrument of that observation is released. The view then drops
the entry. It does not fall back to the assertion the withdrawn one superseded.
A withdrawn entry can be re-asserted only by a new assertion with
`supersedes_id` = the withdrawn row. The assertion and the provision versions
that cite it stay on record. The active tree changes when the document is next
replayed. Record with `tools/withdraw_toc_disposition.py` (dry run by default,
`--apply`). Before it writes, it checks that the cited export holds the answer
with that choice. First case: doc 1457, assertion 17 (export f q1 `body`).

### `source_same_text_copy` — a second file of the same text

Migration 0062. Sometimes two landed files print the same legal text and
differ only in page furniture: page numbers, and "Cont…P/N" page-turn lines.
That case is not a byte-identical copy (0036,
`tools/resolve_exact_instrument_duplicates.py`, which groups by one source
SHA-256), and it is not a partial copy (`source_incompleteness`, 0054).

A row records three things: the copy's landed `source_observation_id`, the
`document_id` that observation produced, and the `canonical_document_id` the
corpus publishes instead. It also holds `observed` (the comparison in words)
and `owner_decision` {`export`, `document_id`, `question_id`, `choice`}.
`evidence` must carry `copy_sha256` and `canonical_sha256` (the two files'
own), `copy_words`, `canonical_words`, `finding` = `page_furniture_only`,
`diff_tool` and `diff_tool_sha256`, and `export_sha256` and `card_sha256`.

The trigger enforces the following:

- the table is append-only (UPDATE, DELETE and TRUNCATE are refused), with one
  row per observation and one per copy document (both UNIQUE); inserts take
  one transaction-scoped advisory lock, so two concurrent records cannot both
  pass the chain checks;
- the observation landed and produced the document;
- the two documents are different files, and the evidence hashes are theirs;
- the canonical document is active and has an active, non-duplicate
  instrument;
- there are no chains: a canonical document is never recorded as a copy, and
  a copy is never anyone's canonical;
- no instrument of the copy's observation is released;
- the owner decision cites one of the two documents, and its `choice` names
  the direction.

**The direction convention.** A decision-review card that asks which of two
copies to keep offers one option per document, named `keep-<document id>`
(2191 q2: `keep-2191`). A row is admitted only when
`owner_decision.choice` = `'keep-' || canonical_document_id`. The trigger and
the recorder both check it, so a record can never retire the document the
owner chose to keep. A future card that asks the same question must name its
options this way.

Like 0054, the record is about sources. The `duplicate_of` flag that keeps the
copy out of `v_release_instrument` is derived from it, and
`tools/apply_source_same_text_copy.py` re-applies it after every replay
(`tools/post_replay_sequence.sh` step 2b). That tool links each active
expression of the copy to the canonical's active instrument at the same
ordinal. When the canonical has been replayed, it advances a pointer that
still names the canonical's earlier revision. A first link re-checks
`v_release_instrument` inside its UPDATE, so a copy released between the read
and the write is never flagged. It skips a released copy, a copy pointing
somewhere else, or a canonical document with no active instrument, and
reports the case. A copy linked on only some of its expression ordinals (the
canonical lacks the others) is a partial link: the run writes nothing and
exits non-zero.

`tools/record_source_same_text_copy.py` records a row (dry run by default,
`--apply`). It aligns every text block of both documents word by word. It
refuses unless every difference consists only of page furniture: a block made
entirely of page numbers and page-turn tokens, or the page's own number
standing first or last on the page. It also checks that the cited export holds
the answer. The release views are unchanged, and the copy stays fail-closed
under the ordinary gates until the link exists. First case: 2673 → 2191
(export i, 2191 q2 `keep-2191`).

### `source_non_authoritative_copy` — a landed file that is not the law's text

Migration 0065. Some landed files are not expressions of the law at all.
docs/02 §4.1 links OFFICIAL English, Urdu and Sindhi publications by
instrument identity, and docs/03b puts `authentic_language` on the
instrument. Neither covers these two kinds, which the table's `kind` names:

- `unofficial_translation`: a translation that the file itself, or its
  publisher, says is not authoritative. First case: 4641 → 1522. 4641 is the
  Urdu rendering of the Sindh Agricultural Income Tax (Amendment) Ordinance,
  1997 (XVI of 1997). Its title page misprints "No. X", and its closing note
  says it cannot be used in court.
- `bill_superseded_by_enactment`: a Bill whose enacted text is held. Example:
  4642, the Balochistan Motor Vehicles (Amendment) Bill. The enacted law is
  Act XIV of 2021 (document 4703), whose schedule rates differ from the Bill's.

Such a file is neither partial (0054) nor the same text (0062). Each row names
the `authoritative_document_id` that the corpus publishes instead. Otherwise
the row has 0062's shape: the landed `source_observation_id` and its
`document_id`, `observed`, and `owner_decision`, whose `choice` must read
`keep-<authoritative_document_id>`. `evidence` must carry `copy_sha256` and
`authoritative_sha256` (the two files' own), `finding` (equal to `kind`),
`basis`, `reviewer_type` and `export_sha256`.

The trigger is 0062's guard set, restated for this table:

- append-only, with one row per observation and one per document, and an
  advisory lock on insert;
- the observation landed and produced the document;
- the two documents are different files, and the hashes are theirs;
- the authoritative document is active and has an active, non-duplicate
  instrument;
- there are no chains through this table;
- no instrument of the observation is released;
- the owner decision cites one of the two documents and keeps the
  authoritative one.

`tools/apply_source_non_authoritative_copy.py` derives `duplicate_of` after
every replay (`tools/post_replay_sequence.sh` step 2b2). It imports 0062's
decisions (`plan`, `FIRST_LINK`, `ADVANCE`), so every copy route follows one
set of rules, and audit C9 checks the link. The release views are unchanged.
When the translation link of docs/03b is built, an unofficial translation may
be shown beside the authentic text, labelled as a translation. Until then it is
withheld.

A wrong file has no authoritative document to point at. An example is 4520,
catalogued as service rules but in fact the Journalist Welfare Fund notice.
Such a file is not recorded here, and it stays counted as blocked until the
right file is landed. (4520 was later released for what it is, as the 2019
Journalist Welfare Fund notification.)

### `statutory_repeal` — a statute repealed by an Act the corpus holds

Migration 0066. This is the corpus's only source of lifecycle status, and it
records one thing: a released **Act** we hold prints a whole-enactment repeal,
"<Title>, <year> … is (hereby) repealed" or "shall stand repealed". docs/03b
draws the line this record keeps. Statute text can show "repealed by another
statute". It cannot show whether a law ever came into force (commencement is
in Gazette notifications), or whether a court struck it down.

A clause is recorded only when all of the following hold:

- it names one released instrument of the **same jurisdiction**, by an exact
  title and year (folded for case, punctuation, footnote markers and the old
  spelling "Sind");
- no partial or qualifying words stand before or after it, such as "in its
  application to", "so far as", "to the extent", "except" or "section N of";
- no released provision speaks of **reviving** that enactment;
- the repealing instrument is an Act. An Ordinance's repeal can lapse with the
  Ordinance, and that is a legal question the recorder does not settle.

The record names both sides by source observation and expression ordinal. The
repealing provision is named by its first block and its path below the three
identity labels, and the clause is kept verbatim.

`repealed_on` is set only where the repealing Act prints a single bracketed
date under its title **and** says it "shall come into force at once". The
`repealed_on_basis` field says so. instrument's `ck_repeal` (0004) allows status
`repealed` only with a date. So, after every replay,
`tools/apply_statutory_repeals.py` (post-replay step 2b3) gives:

- a **dated** repeal: status `repealed`, `repealed_on` and `repealed_by_id`;
- an **undated** repeal: `repealed_by_id` only, status `unknown`;
- anything else: unchanged.

Audit A14 checks the derivation both ways. Release views do not read status: a
repealed law stays released and queryable ("repeal with savings"). Withdrawal
is a later row with `assertion` set to `withdrawn` (append-only; latest wins).

`tools/record_statutory_repeals.py` finds and records rows (dry run by
default, `--all` to list them all).

First run, 20 Oct 2026: 571 whole-enactment clauses. Of these, 283 name a law
we do not hold, 151 are in Ordinances, 108 are qualified, 4 are revived and 1
names its own Act. That left 50 instruments, 24 of them dated. Every other
instrument's status is `unknown`, a declared limitation and not "in force".

Second pass, 11 Nov 2026: 16 of the 54 undated repeals were dated from the
repealing Act's established commencement (0070): 12 by exactly the rule above,
4 where the Act prints its own commencement date
(`tools/evidence/date-statutory-repeals-from-commencement-2026-11-11.sql`,
method `nizam.statutory_repeal_dated_by_commencement/1`). That gives 62 repealed
and dated, and 38 with a certain repealer but no date.

Third pass, 16 Nov 2026. Four changes to the recorder, each found by reading
the clauses it would record:

- **The portal's repeal note is not part of a title.** 40 catalogue titles
  carry it: `Boilers Act, 1923(Repeal by Ord. 52 of 2001, S, 610)`, `(Repealed
  vide Act XVIII of 2020) THE AZAD JAMMU AND KASHMIR …`, or a cut note's
  stray `)`. The Python title key (`PORTAL_REPEAL_NOTE`) and the SQL
  `instrument_title_key` (migration 0081) both strip it. Before this, those laws
  could not match the clause that repeals them, and the as-made and
  consolidated texts of the Commissions of Inquiry Act could not be linked as
  twins.
- **The display title is matched too.** This is the name verified in the law's
  own print. One instrument counts once, however many of its titles match.
- **Several hits can still be one answer.** When every pair of hits is a
  standing consolidated twin, the clause repeals one law, so each text gets its
  own row. A14 needs each `repealed` to rest on its own row. Otherwise, the
  one hit of the kind the clause names wins. This settled 4212, whose kind was
  misread as `regulation` from "… and Regulation of Cooperative Banking Act".
  Anything else stays ambiguous.
- **Two shapes are refused** (they were recorded wrongly in trial):
  - something *of* an Act: "… section 28 (1) (g) of the University of Karachi
    Act, 1972 are hereby repealed" (2458; the segmenter split the sentence at
    "(g)");
  - a title that runs on past its year: "The Bombay District Police Act, 1890
    (Repeal) Ordinance, 1955, is hereby repealed" repeals the 1955 Ordinance.

  A bracket with a numeral (`(Ordinance No. VIII)`) is still a citation, and a
  list ("X Act … and the Y Ordinance … are hereby repealed") is still a whole
  repeal of each.

Result: 21 new rows, mostly the twin texts of laws already repealed on one
side. The 11 Nov commencement pass was run again over the commencements the
16 Nov date work established, and dated 17 more. That gives 87 repealed and
dated, and 64 with a certain repealer but no date (151 laws). One earlier row
(Indian Electricity Act, 1903) is no longer reproduced, because a newly
released Repealing and Amending Act, 1914 carries a generic "nor shall the
repeal … revive" next to that title. The recorder never withdraws a row, and
this one stands.

### `instrument_metadata_assertion` — names, numbers, dates and language from evidence

Migration 0070. Append-only; keyed by `(source_observation_id,
expression_ordinal, field)` so a replay does not orphan it; latest row wins, and
a withdrawal is a row with `assertion = 'withdrawn'`. One field per row:

| field | recorded by | rule |
|---|---|---|
| `display_title` | `tools/record_display_titles.py` | the name verified or near-matched in the instrument's own printed text (`.artifacts/instrument-names-2026-11-11/`); names needing review are not recorded. **`--short-title-clause` (16 Nov 2026)**, for laws with none: the law's own "may be called …" clause checks the catalogue title. If they agree (≥85% of words), the cleaned catalogue title is kept. If the catalogue title is a file name or abbreviation ("Baln", "NA-", ".docx"), the clause's name is recorded. If they disagree, nothing is recorded. 1,239 recorded, plus 9 page-read (`tools/evidence/display-titles-*-2026-11-16.sql`), including three historical Gazette scans whose catalogue title named a different law (9067 is Act XXVII of 1870, not the Penal Code; 8846 is Act I of 1896; 6688 is the Civil Pioneer Force (Amendment) Ordinance, 1943). Their stored `year` is still the catalogue's: an open defect |
| `number` | `tools/record_instrument_numbers.py` (`--correct-stored`: a segmenter number that disagrees with the one printed number is replaced, basis `printed_number_corrects_stored`; 29 on 12 Nov 2026, plus 1707 by hand) | printed in the **title region** (first ≤80 blocks, cut at long title / preamble / enacting formula / section 1 in body form; first 20 blocks when no marker); year equal to the instrument's; kind word agrees; canonical numeral; exactly one candidate |
| `enacted_on` | `tools/record_enacted_dates.py` | read in the title region. **v1:** the bracketed date under the title (`[18th April, 1956]`) or a printed assent statement. **v2, 16 Nov 2026:** also "assented to by the Governor … on …"; "made / promulgated by the President … on …" (Ordinances, Orders, Regulations); a block that is only a date under the title; and, for Rules, Regulations, Notifications and Orders only, the notification's own line ("Dated Lahore, the …", "No. …, dated 2.11.2004"). Refused: Gazette mastheads, "Dated …" lines on Acts and Ordinances (publication), "Updated till", draft rules, two-digit years. The year must equal the instrument's, or (Acts and Ordinances) its printed number's year within 2. **Precedence:** assent or promulgation statement > bracket > date line > notification line. The most direct form present must give exactly one date; lower forms that disagree are kept in the evidence. The catalogue date is **not** a source (placeholders and upload dates) |
| `commenced_on` | `tools/record_commencement.py` | only a self-executing commencement of the **whole** instrument: "at once" gives the established `enacted_on` (0066's convention), or a printed "on <date>". **General clauses default (16 Nov 2026)** for an Act silent on its commencement: federal GCA 1897 s.5(1), the day of assent, only from a printed assent statement; Punjab / KP / Balochistan GCA 1956 s.3, the first publication, whose date "shall be printed either above or below the title", only from that printed date. Not Sindh or AJK, whose general clauses sections are not held. Notification, partial, enumerated or deemed commencement is never recorded (docs/03b: commencement lives in the Gazette) |
| `long_title` | `tools/record_long_titles.py` (0083) | the printed long title, capitalised as a title ("AN ACT to …", "An Ordinance further to …"), to the end of its sentence. It is read in the first 80 blocks, and up to 400 only when none is printed there, never past section 1's body. Exactly one distinct title. Refused when it is cut short (ends on a function word), takes in a neighbouring Gazette column ("; (c)", a numbered subsection), or carries preamble or printer words ("expedient", "hereby enacted", "Printed by", "Gazette"). 16 Nov 2026: 6,394 recorded (80% of Acts, 85% of Ordinances) |
| `status` | `tools/record_status.py` (0082) | `in_force` only for an **Act** that has commenced (established `commenced_on`, "shall come into force at once", or silent under its general clauses statute) **and** against which no repeal is known: no standing statutory repeal, no portal repeal note, and no released provision of another law naming it in a whole, territorial or extent-limited repeal, cease or omit clause. Never Ordinances (lapse is a constitutional question) or subordinate instruments (they stand with an enabling law the corpus does not link). Not covered, and stated on every row: repeal by a law not held, judicial invalidation, extent. Everything else stays `unknown` |
| `text_language` | `tools/record_text_language.py` | Arabic-script share of all released text ≥ 0.60 gives `ur` (or `sd` with Sindhi letters), ≤ 0.10 gives `en`; anything else is left for a person |

Printed facts (`number`, `enacted_on`, `commenced_on`), and `status` (0082),
must carry the verbatim `quote` and the `source_block_id`. The guard checks that
the block belongs to the observation. Recorders re-check their own earlier
assertions under the current rules, and withdraw what is no longer reproduced.
They never re-assert a withdrawn key. There is one exception (16 Nov 2026,
`record_enacted_dates.py`): a key withdrawn on recheck (`recheck_not_reproduced`)
by the same method version may be asserted again when that version reproduces a
date. A person's withdrawal, or another method's, stands for good.

**Lapsed Ordinances (0085, 16 Nov 2026).** `status = 'lapsed'` comes from the
corpus's own Constitution (doc 4419). Under Art. 89(2), a President's
Ordinance "shall stand repealed at the expiration of one hundred and twenty
days", extendable once, so it lives at most 240 days. Under Art. 128(2), a
Governor's Ordinance lives at most 180 days.

It is asserted only for a federal or provincial Ordinance promulgated under
that wording, i.e. on or after the Eighteenth Amendment's commencement on
2010-04-20 (doc 4434). The footnotes do not print the words that amendment
replaced, so the corpus states no rule for earlier Ordinances. Three further
conditions apply:

- its year is printed in its own title;
- it is at least a year past its latest possible lapse;
- no repeal of it stands, and no law in the corpus continues it or deems it
  an Act.

16 Nov 2026: 101 lapsed. `operative_provision` stops serving a lapsed
Ordinance only after its *latest* possible lapse, because disapproval or an
Act can end it sooner. Not asserted:

- Ordinances that Art. 270A (1977–85) and Art. 270AA (12 Oct 1999 – 31 Dec
  2003) continue. Whether one was still in force on the dates those Articles
  name depends on regime orders the corpus does not hold.
- Ordinances of 1973–2010.
- AJK and GB Ordinances.

**Currency (0088, 16 Nov 2026).** Every released law has a currency in
`v_instrument_currency`, with a reason and the earliest date the evidence
proves it stopped being law. Owner instruction: "do something about these
unknown so it is not a problem". `operative_provision` carries `currency` and
`currency_reason` on every row.

- **`current`:** `in_force`.
- **`not_current`:** repealed; lapsed; a repeal certain but undated, from the
  repealer's commencement or else its enactment; replaced by a later Act of
  the same name (0067; owner q6 "shown as replaced"), from the successor's
  enactment; or the official portal marks it repealed.
- **`historical`:** a place outside Pakistan, or a pre-1947 text no
  consolidated code publishes; from 1947-08-15.
- **`current_unverified`:** everything else.

The view stops serving `not_current` and `historical` laws from that date.
`current_unverified` laws are still served, with their reason.
`tools/record_status.py` records every status it cannot assert as
`value = 'unknown'`, with the reason as its basis: commencement by
notification, an Ordinance before the current Art. 89 text, an AJK Ordinance
(the AJK Interim Constitution itself is not held), or a subordinate
instrument whose enabling law is not linked. So no law is silently unknown.

16 Nov 2026: 2,579 current, 6,544 current_unverified, 550 not_current, 639
historical. Known cost: the Companies Ordinance, 1984 counts as replaced,
although s.509 of the 2017 Act keeps its Part VIIIA in force. Questions on
that Part abstain until partial repeals are modelled.

**Owner presumption of force (16 Nov 2026, as built).** Owner decision: "i
don't research online read for remaining law or considered them in force but
everything must be citable and referanceable". `tools/record_status.py`
(`OWNER_PRESUMPTION = True`) now records each status it cannot assert from a
text as `value = 'in_force'`, with basis `owner_presumption_in_force`. The
evidence carries `reviewer_type: "owner"`, the decision quoted, and
`presumed_over`: the reason code that would otherwise have been recorded as
`unknown`.

The presumption never overrides evidence, so some codes are not presumed
(`NOT_PRESUMED`):
- a statutory repeal that stands;
- a portal repeal note;
- a pre-independence text that no consolidated code publishes;
- any `…_enabling_law_historical`.

Lapse, replacement and repeal rows still win, because currency reads them
before status. First run: 5,886 presumed. Serving snapshot after it: 8,253
current, 0 current_unverified, 1,362 not_current, 646 historical. On 17 Nov the pre-independence exclusion was
extended to Ordinances (`pre_independence_archive_text`); 31 archive Ordinances had escaped it. The snapshot is
now 8,243 current, 1,369 not_current and 676 historical.

The presumption is a row, not a rewrite. Finding a repeal later supersedes it
in the usual way; to withdraw the presumption wholesale, run the tool with
`OWNER_PRESUMPTION = False`, which records `unknown` again under the same keys.

**Known costs, found while authoring golden sets 2–4 (16 Nov 2026).**

1. **A repeal the title match missed.** The AJK Rent Restriction Act, 1986
   s.26 repeals "the Azad Jammu and Kashmir Rent Restriction Act, 1952", but
   both held texts of that law are titled "The Azad Kashmir Rent Restriction
   Act, 1952". No repeal was matched, and the presumption made the 1952 Act
   current. It is now recorded from the page-read clause
   (`tools/evidence/ajk-rent-1952-repealed-by-1986-2026-11-16.sql`) and is
   `not_current` from 1986-03-05.
   The deeper cause was a **list repeal**: "The … Act, 1952 (…) and … Ordinance,
   1986 … are hereby repealed". Only the first title of a list was ever read,
   and here an OCR-damaged bracket hid even that. `record_statutory_repeals.py`
   now reads every title of a list (`listed_repeals`). It also folds one place
   under several names (Azad Kashmir / Azad Jammu and Kashmir / AJK, N.W.F.P. /
   Khyber Pakhtunkhwa, Baluchistan / Balochistan). This found 9 more whole
   repeals.
2. **Repeals confined to one territory, and printed extent: fixed by 0095,
   0100.** See "Where a law runs" below.
3. **Text history before capture: fixed by 0096–0099, conservatively.** See
   "How far back the held text is the law" below.

### Where a law runs: extent clauses and territorial repeals (0095, 0100)

**Extent.** `tools/record_territorial_extent.py` reads a federal-text law's own
extent clause, "It extends to …". It records instrument_metadata_assertion
field `territorial_extent`: the territories as a comma list, with the clause
verbatim and its source block. Where one stands it decides the law's reach;
otherwise `territory_reach3`'s title reading stands. `extent_basis` says which.

A clause is read only when every word of it maps to a territory:
- the whole of Pakistan, or all the territories of Pakistan;
- West Pakistan: the four provinces, since its excepted tribal and special
  areas lie inside them;
- each province, by its current or older name;
- ICT;
- "all the provinces" only together with the capital.

"The capital of the Federation" and "the Federal Capital" are resolved by the
law's year. They mean Karachi (Sindh) in laws of 1948–1960, Islamabad from
1963, and are not read for 1961–1962. "Sections 13 and 17 of this Act shall
extend to …" is the extent of some sections, not of the law, and is not read.

First run: 1,128 laws read. 61 changed reach from the title reading; for
example, the Hindu Marriage Act, 2017 now runs in ICT, Balochistan, KP and
Punjab, not Sindh.

**Territorial repeal.** The table `territorial_repeal` is append-only, latest
wins, and keyed like `statutory_repeal`. `tools/record_territorial_repeals.py`
records a released Act repealing a **federal-text** law for one territory:
- a provincial Act's repeal, which operates in its own province only;
- a clause that itself says "to the extent of" or "in its application to" a
  territory, where that territory is the repealer's own, or ICT for a federal
  law.

Any other qualifier, a federal repeal not confined to ICT, an ambiguous title
or a revival is skipped.

The record never sets `instrument.status`: the law stays in force elsewhere.
`v_instrument_currency.territory_exits` maps each territory to the date the law
left it. That date is the printed one, else the repealer's commencement, its
enactment, or 1 January of its year. A law that has left every territory it
reached is `not_current`, with reason `repealed_in_each_territory`.

`operative_provision` stops serving a law in a territory from its exit date.
A read without `nzq.territory` still returns it, with `territory_exits`.

First run: 47 rows. Among them:
- the Child Marriage Restraint Act, 1929 left ICT (2025-05-29), Balochistan
  (2025-11-18) and Punjab (2026-05-11);
- the Defamation Ordinance, 2002 left Punjab (2024-06-07);
- the Control of Narcotic Substances Act, 1997 left Sindh;
- the Pakistan Arms Ordinance, 1965 left Balochistan;
- the Canal and Drainage Act, 1873, which runs only in Punjab, is not current.

0100 made the exit test NULL-safe. As 0095 shipped it, a law with no exit was
served in no territory at all. The golden-set build caught this on the same
day, and `tests/test_territorial_serving.py` pins it.

Audit A17 checks that these records are consistent.

### How far back the held text is the law (0096–0099)

Each `provision_version` is still written `daterange(<capture>, NULL)`. The
replay writes it, and it is not edited. What is new is the view
`mv_provision_text_known_from` (refreshed by `tools/refresh_serving.py`, and
checked by A16). It holds, per provision of a served law, the earliest date
the held text, consolidated at capture, is **known** to have been the law.
`operative_provision` serves the single open version from that date.

The date is decided **per law** (0098):
- **Any undated amendment.** If any amendment footnote of the law has no
  recoverable date, or any provision's own text carries more amendment markers
  than the dated references aimed at it, the whole law is unknown before
  capture (`an_amendment_is_undated`). One provision's undated change proves
  nothing about the silence of the others.
- **Every amendment dated.** The date is the latest of the law's start, its
  dated amendment references, and the held "(… Amendment)" laws whose titles
  name it (`after_latest_recorded_amendment`).
- **No amendment evidence at all.** The date is the law's start
  (`no_amendment_recorded`).

Where only a year is known, a date means 31 December of it, never 1 January.
So a law is not served before it existed.

The markers counted (0099):
- an opening insertion mark, `1[` or `2[:]`, where the digits are not part of a
  year or a decimal;
- a closing `]` with no letter after it, beyond the plain brackets the same
  text opens;
- an omission mark, `5* * *`.

Gazette running heads ("DECEMBER 18,2020 [PART I") and OCR noise are not
counted.

Measured 16 Nov 2026:

| Basis | Laws | Provisions |
|---|---|---|
| `no_amendment_recorded` | 6,022 | 433,165 |
| `after_latest_recorded_amendment` | 376 | 39,555 |
| `an_amendment_is_undated` | 3,856 | 652,601 |

The PPC, the Constitution, the MFLO and the Punjab text of the 1929
child-marriage Act are among the undated ones. They stay unservable before
capture until their amendment footnotes are dated.

**Residual risk:** a text that was amended but prints no marker, has no
footnote and has no held amending law is served back to its start.

0096 also pinned `search_path` on every SQL and plpgsql function of ours,
because a materialized view is built under a restricted path.

**Ordinance lapse, widened (0091, 0092; 16 Nov 2026).** The Eighteenth
Amendment's own text is held as doc 4434. Its s.27 substitutes "for the words
'four months' the words 'one hundred and twenty days'" in Art. 89(2)(a)(i)
and (ii), and inserts the extension proviso. Its s.41 does the same for "three
months" in Art. 128. Art. 89's footnotes (doc 4419) list every amendment of
it: P.O. 14 of 1985, P.O. 20 of 1985 and the Eighteenth Amendment. So
Ordinances promulgated from 1 Jan 1986 to 19 Apr 2010 stood repealed four
months (federal) or three months (provincial) after promulgation, with no
extension. Excluded are the Art. 270AA window (12 Oct 1999 – 31 Dec 2003) and
everything before 1986.

AJK has its own rule, from the Interim Constitution, 1974, Art. 41(2)(a): four
months, extendable once by four. That text was read from the official file
`https://law.gok.pk/wp-content/uploads/2023/10/AJK-interim-constitution.pdf`
(sha256 `5901ea06…`, staged and not landed). The Interim Constitution has no
affirmation or validation article, and no AJK law continues Ordinances
generally, so it is applied to AJK Ordinances of 1975 onward. A continued
Ordinance (270A, 270AA, or pre-1973) that a held law amended after its window
was alive then. It is tested as an Act (38 in force).

Result: 1,064 Ordinances lapsed. The ones still unverified carry their window
as the reason: `ordinance_continued_by_art270A_1977_1985`,
`…art270AA_1999_2003`, `ordinance_of_a_pre_1973_regime`,
`ajk_ordinance_before_interim_constitution`.

Searched and not found:
- Pakistan Code (the Ministry of Law's consolidation) publishes no in-force
  register. Its disclaimer says the laws "should not be taken as authentic".
- The corpus holds no commencement notification.
- The Sindh Code does not publish the Sindh General Clauses Act, 1956 (only
  its 2002 amendment).
- The held West Pakistan General Clauses Act, 1956 (8538) is too OCR-damaged
  to read s.3.

**Serving snapshot (0093, 0094).** `operative_provision` used to re-derive
every law's release, currency and reach on each read: 7 min 25 s for one
territory. It now reads `mv_instrument_serving`, a per-law snapshot of release,
currency, reach, twin-level repeal, supersession and historical window. One
territory now reads in 8.7 s, the whole corpus in 18.7 s. The date and
territory tests stay in the view. `tools/refresh_serving.py` refreshes the
snapshot and runs at the end of `post_replay_sequence.sh`. Audit A16 fails
while the snapshot differs from the live derivation.

**Territorial reach (0086, 0087).** Owner rule, 16 Nov 2026: "each provincial
jurisdiction in their own provinces while federal is for all". With
`nzq.territory` set, `operative_provision` serves a province's, ICT's, AJK's
or GB's own law there. Federal law is served in all four provinces and ICT,
except where its printed title confines it (`territory_reach3`):

- **West Pakistan:** the four provinces.
- **Islamabad / Capital Territory:** ICT.
- **A named province, or a city's own law** (rent, municipal, courts, port):
  that province.
- **Places outside Pakistan** (Bengal, Oudh, Burma, East Pakistan, Delhi …):
  nowhere, unless Pakistan Code publishes the text as current law.

Federal forces (Frontier Corps and Constabulary) and federal charters of an
institution in a city reach everywhere. AJK and GB get their own law only: a
federal Act runs there only as adapted or extended. `extent_coverage` names
the rule: `own_territory`, `title_named_territory` or `jurisdiction_default`.

`territory_reach3` is a plpgsql function evaluated per row. A whole-territory
scan of the view takes minutes, so retrieval (L3) should precompute it per
instrument.

**Official source URLs (16 Nov 2026).** 53 released laws had no
`source_url`. All came from the original scrapes, and all have an apostrophe
in their title: the scrapers lost the URL when sanitising the file name. Each
was matched to the portal listing or the August scrape manifest. It was
accepted only when the official PDF is byte-identical to the held blob (a
live fetch, or the manifest's recorded sha256 where the portal re-generates
PDFs). Only a NULL `canonical_url` was filled, with the proof in
`source_metadata.canonical_url_traced`
(`tools/evidence/official-urls-traced-2026-11-16*.sql`). Every released law
now has its official URL.

What the dates mean. On a provincial Act the date under the title is, by the
general clauses statute, the date of first publication. On a Pakistan Code text
it is the consolidator's print. Measured on the twin pairs, it equals the
Gazette assent statement in 4 of 7 cases and falls 2–12 days later in 3. So
`enacted_on` can be a few days after assent, never before it. That direction is
the safe one for `operative_provision` ("not yet enacted at `as_of`").

### Partial repeals and the units a repeal excepts (0102, 0103)

`provision_repeal` (0102) records a unit a later law repeals or omits: a section, sub-section, clause, Part,
Chapter or Article. `provision_survival` (0103) records a unit a whole repeal expressly excepts. Both are
append-only and source-keyed, like `statutory_repeal`. The unit is named by its relative provision path within
the expression (`s_27.ss_2`, `pt_VIII.s_282_A`), so a replay does not orphan it.
`tools/record_provision_repeals.py` writes both (post_replay_sequence step 4a2), and `tools/refresh_serving.py`
refreshes `mv_provision_repeal` and `mv_provision_survival`. Audit A18 checks that every standing row resolves to
exactly one held provision, that the territory follows the rule, and that both snapshots equal the live sets.

A clause is read only when it is a plain list of units of one named law followed by the verb. Ranges ('121 to
147', '282A to 282N'), sub-section ranges ('(2) to (6)'), lists spanning two laws and a printed date ('shall,
as from the first day of July, 1962, stand repealed') are read. An amendment of words ('in section 2, the words
...'), a schedule 'to' another law, or a qualifier by subject ('in relation to the subject matter of this Act')
is not.

A unit is recorded only when it resolves to exactly one held provision outside the schedules, and its held text
is live. A unit the consolidation already prints as omitted counts as reflected; a unit with an amendment mark
may have been re-enacted after the repeal. Both are reported, not recorded. The repeal date is the printed one,
else the repealer's commencement, enactment, or 1 January of its year (as 0095).

Measured 17 Nov 2026: 34 repealed units in 12 laws. Examples: Electronic Transactions Ordinance ss.36–37
(PECA 2016); Patents and Designs Act ss.43–54 (Registered Designs Ordinance 2000); the Lahore Development
Authority and Punjab Development of Cities Act units (Punjab Water and Sanitation Authority Act 2025); Sindh
Finance Act 1994 s.9, still printed in its consolidated text and served as law until 0102. 16 excepted units in
2 laws: Companies Ordinance 1984 ss.282A–282N, and PIA Corporation (Conversion) Act 2016 s.7(1), held as s.7's
own words, so subtree false. Each such clause also records the whole repeal in `statutory_repeal` (method
`nizam.repeal_except_units/1`), which `record_statutory_repeals.py` skips because of the 'except'.

### Year and kind from the law's own text (0101)

`instrument_metadata_assertion` also takes `year` and `kind`. A standing row corrects the catalogue value the
segmenter wrote, and `apply_instrument_metadata.py` re-applies it after every replay; A15 checks it is reflected.
Each needs the verbatim clause and its source block. Five laws are corrected
(`tools/evidence/catalogue-corrections-2026-11-17.sql`):

- 6688 is an Ordinance of 1943;
- 8846 is Act I of 1896;
- 9067 is Act XXVII of 1870;
- 11382 is of 2014;
- 11379 is Rules.

The provision path keeps the catalogue year and kind it was minted with, because it is the lineage key, not a
citation.

### `amendment_reference` — which law amended which provision

Migration 0072 (resolution refined by 0073, 0074). Append-only. One row is one
printed amendment footnote entry of a released expression, verbatim:
`1Subs. by the Law Reforms Ordinance, 1972 (XII of 1972), s. 2`. Each row is
parsed into `operations`, the cited law (`cited_title` / `kind` / `number` /
`year` / `section`) and a printed `effective_from` (w.e.f.).

`target_block_id` is the one body block on the same page that carries the same
footnote marker before `[` or `*`. It is NULL when no single block does.

`v_amendment_reference_current` resolves:

- the amended instrument and provision;
- the amending instrument, only on **exactly one** match. A named citation
  matches by title key and year. Only a bare `Act IV of 2011` matches by
  number, never a West Pakistan citation. A citation that names a jurisdiction
  matches only within it. An abbreviated citation with no parsed title
  (`F.A.O., 1975`) matches through a reviewed `citation_abbreviation` row
  (0078), then by that row's title and year.

`citation_abbreviation` (0078) is append-only; the latest row per abbreviation,
year and jurisdiction wins. A row gives the printed abbreviation, a pattern
anchored at the start of the cited text, the title it stands for, and the
corpus print that shows it (`evidence.printed`). The texts print no key to
their abbreviations, so a row needs a footnote that glosses the abbreviation
or prints the same amendment in full. Recorded 14 Nov 2026: `F.A.O., 1975` →
Federal Adaptation of Laws Order (305 footnotes). Not recorded: `A.O., 1937`,
`1961` and `1964` (Orders not held), `A.O., 1949` (no corpus gloss), and
`Baln. A.O. of 1975` (Order not held).

Migration 0084 (16 Nov 2026) resolves four more shapes, each to one answer:

- **Title, "No." and number:** "the Repealing Act No. XVI of 1874". Resolved
  by number when the printed words agree with the candidate's title.
- **A title the parser cut at a bracket or comma:** "Revision and Declaration)
  Ordinance, 1981". Resolved when it is the *end* of exactly one same-year,
  same-jurisdiction title.
- **A provincial law citing its own province's law:** a candidate in that
  province is preferred, when the amended law's title names the province.
- **A Constitution amendment held only as a provincial reprint.**

Result: 4,757 → 4,999 resolved, and no earlier resolution changed. Still
unresolved, by design:

- 2,116 cite laws the corpus does not hold (Indian amending Acts of
  1880–1946);
- about 2,300 cite a number that the corpus's (OCR) copy does not carry;
- citations shared by a federal and a provincial law, which stay ambiguous.

This is docs/03b's `amends` relation **without version history**. The corpus
holds only current consolidated wording, so no version is closed or opened.

### `legal_edge` — docs/03b §6's edge relation, as a view

Migration 0079. docs/03b designs a table of provision and instrument uuids with
`ON DELETE CASCADE`. Here a replay retires a tree and mints new ids, so stored
edges would cascade away or go stale on the next repair. The decision (lead, 14
Nov 2026, standing delegation) was therefore to make `legal_edge` a **view**
over the source-keyed records, in docs/03b's columns (`kind edge_kind`, one
`src_*`, one `dst_*`, `validity`, `raw_text`, `confidence`, `method`,
`verified_by`). Two columns are added: `source_relation` and `source_id` name
the record behind each edge.

- **`amends`.** Built from `v_amendment_reference_current`. The source is the
  amending instrument. The destination is the provision carrying the footnote
  marker, or else the amended instrument. Validity runs from the printed
  w.e.f. date.
- **`repeals`.** Built from `v_statutory_repeal_current`. The source is the
  repealing clause's provision, resolved from `repealing_relative_path`, and
  the destination is the repealed instrument. Validity runs from the repeal
  date.

- **`empowers` (0089, 16 Nov 2026).** Built from `v_delegation_current`.
  The source is the enabling section, or the parent law when the section does
  not resolve. The destination is the subordinate instrument.
  `tools/record_delegation.py` reads the instrument's own enacting formula
  ("In exercise of the powers conferred by section 25 of the Balochistan Civil
  Servants Act, 1974 …"). It records a link only when the named law and year
  resolve to one released law: same jurisdiction first, else the federation.
  Several texts of one law count as one: the consolidated text wins over an
  as-made copy; otherwise the fullest text, with `texts_of_one_law` in the
  evidence.

  First run: 1,042 of 2,600 subordinate instruments linked to 292 parent
  laws, 1,003 of them to the enabling section. 1,311 print no readable
  formula; 247 name a law not held. The same tool records "in supersession of
  the … Rules, YYYY" (not partial) as `instrument_supersession` basis
  `supersession_clause`. That gave one row: the corpus seldom holds the
  superseded instrument.

  The currency reason of a subordinate instrument names its parent's currency.
  A parent that is `historical` makes the instrument historical (0090). A
  parent that is `not_current` does not: under GCA s.24, rules survive a
  repeal-and-re-enactment. So it stays `current_unverified`, with the reason
  `…_enabling_law_not_current`.

- **`refers_to`, `subject_to`, `notwithstanding` and `defines` (0114,
  0115, 21 Nov 2026, D-108).** Built from the two derived tables below.
  Resolved references only: an unresolved one is kept in its table, but it
  is not an edge.

An edge appears only when both ends resolve. First measured, 14 Nov 2026: 4,620
`amends` edges (3,242 to a provision) and 129 `repeals` edges, all from a
clause. `contains` is the ltree. Supersession and consolidated twins relate
versions of one law, so they are not edges. Six kinds have no recorded relation
yet: `saves` beyond 0103, `commences`, `defaults_from` (applied at read time,
below), `interpreted_by`, `invalidated_by` and `attracts`.

### `provision_reference`, `provision_definition`, `provision_link_state` — the links a provision's words make

Migrations 0114 and 0115 (D-108). These are **derived index artefacts**, like
`chunk` (0108), not evidence. `nizam.workers.links` builds them from the
release, using the pure rules of `nizam.storage.linking`, under one named rule
(`linker`, `nizam.links/7` on 21 Nov 2026). A rule change is a rebuild
(`--rebuild`). An ordinary run relinks only the laws that need it: a law with a
new or retired version, or with a row pointing at something that has left the
release. Audit **A23** asserts that the tables are exactly the release under one
linker, and that nothing they point at is outside it. Operative status is never
decided here: readers ask `operative_provision` at their own `as_of`.

- **`provision_reference`.** One row is one printed naming of a unit or
  schedule.
  - `kind` is the phrase: `notwithstanding`; `subject_to` ("subject to", "save
    as / except as provided", "without prejudice to"); otherwise `refers_to`.
    The phrase governs a reference only when nothing else is named between them
    and no new clause starts.
  - `label` is the label as printed, with "295 C" folded to `295C`, "4-A" to
    `4A`, and decimals like `12.1` kept.
  - `other_law` is the other law as printed, when the words name one.
  - `dst_unit_id` and `dst_instrument_id` give the resolved destination.
  - `in_heading` marks a reference read from the heading or marginal note
    ("[See section 5]" above a schedule); its offsets are then into the heading.

  **Resolution.**
  - **Same law.** A unit with that label; "Article N" asks only for articles (a
    constitution's or an Order's sections count); a schedule by its printed
    number, or the law's only schedule.
  - **Subordinate instruments** (Rules, Regulations, Notifications). A bare
    "section N" names the parent law (empowers, 0089); "rule N" names their own
    unit, as does "section N of these rules".
  - **Another law.**
    - "the Act" / "the Ordinance" is the parent, when its kind matches.
    - A title resolves by `instrument_title_key` and year: a title naming its
      province in that province; AJK and GB own copies first; otherwise federal
      first. Exactly one law must match.
    - A run of references ("sections 161, 164, 165 of the Azad Kashmir Penal
      Code") shares its trailing law.
    - An amending law's section numbers always name another law.

  First full build: 166,321 rows. 67,459 resolve within their own law and 14,491
  to another law; 22,108 within a law and 62,263 to another law do not resolve
  (laws not held, OCR damage, amending text).
- **`provision_definition`.** One row is one word a clause defines ("means",
  "includes", "denotes", "has the meaning").
  - `scope` is read from the opening words. "In this Act" gives `law`. "In this
    Chapter/Part" gives `division`, reaching the units printed after
    `after_ordinal`. "In this section" gives `unit`. A Chapter the tree lacks
    gives `unit`, never the whole law.
  - `empty` marks a definition with nothing after its verb in its node.
  - `continuation` lists the following siblings that carry a flattened
    definition's sub-items.
  - An amending law contributes no definitions.

  72,030 rows: 69,772 law-wide, 462 division-scoped and 1,796 unit-scoped.
- **`provision_link_state`.** Every released version the linker read (A23's
  coverage).

`defaults_from` is applied at read time (nizam.retrieval.assembly). A word a law
does not define takes its parent law's whole-law definition (for a subordinate
instrument), then its jurisdiction's own General Clauses Act's. That Act exists
only where the corpus holds one: federal law the 1897 Act; Punjab and KP their
copies of the 1956 Act. Sindh, Balochistan, AJK and GB have none held, and none
is guessed. Drafting words ("section", "year") and words too general ("person",
place names) are not attached from a General Clauses Act.

### `consolidated_twin` — a law's text as made, linked to its consolidated text

Migration 0075 (basis widened by 0076). About 40 laws are released twice: the
original Gazette issue as made (Ministry of Law DRS, `drs.molaw.gov.pk`) and the
Pakistan Code consolidated text (as amended). These are two versions of one law,
not copies, so 0036, 0054, 0062 and the expression-source-variant route all
refuse them. Owner decision, 12 Nov 2026: keep both released and citable, link
each reviewed pair, and serve only the consolidated text as operative.

A row links the as-made expression (observation, ordinal) to its consolidated
twin. It is append-only and keyed by source; the latest row wins, and a
withdrawal is a row with `assertion = 'withdrawn'`. The trigger requires both
sides to resolve to active canonical instruments of the same jurisdiction, kind
and year, and refuses chains. `v_consolidated_twin_current` resolves the
instruments.

`tools/record_consolidated_twins.py` proposes pairs on identity evidence (same
title, or same number with title words overlapping at least 75%). Numbers that
disagree always refuse, and so does an as-made text with more than one match.
It prints near misses for a person to read. Two pairs whose titles differ in
words were reviewed by hand (basis `same_number_year_title_reviewed`, 0076).
First run, 12 Nov 2026: 34 links.

`operative_provision` leaves out the as-made side of every standing link
(0075). It also treats a repeal recorded on either text as the law's repeal
(0077): six links had the repeal recorded on the as-made text only. The stored
`status` is not copied across, because audit A14 requires each `repealed` to
rest on its own statutory repeal row.

### `chunk` and the lexical indexes — retrieval's storage (0108, D-095)

**`chunk`** holds ordered character offsets (`char_start`, `char_end`) into **one** `provision_version.text_normalised`
(docs/03 §3). It never holds a copy of the text.

| column | |
|---|---|
| `version_id`, `seq` | unique; `ON DELETE CASCADE` from the version |
| `char_start`, `char_end` | checked `0 <= start < end`; a trigger refuses an end past the version's text |
| `context_prefix` | `title \| chapter heading \| unit + section heading \| qualifies: <the rule's opening words>`, ≤ 240 chars. Embedded beside the span, never altering it (docs/02 §5.3) |
| `embedding` | `bit(1024)`, the sign bits of the active generation's vector (`np.packbits(v > 0)`, first dimension first). Nullable by design; audit A21 is the rule (D-098) |
| `jurisdiction` | (0110) `subltree(path, 0, 1)` of the chunk's provision, set by trigger, NOT NULL. The dense scan's scope filter runs on it inside the HNSW scan (docs/04 §4.2); not a serving filter |
| `chunker` | the splitting rule (`nizam.chunking/1`); a change of rule or model is TRUNCATE plus rebuild |

As built, a version holds only its own node's words. A clause does not contain its sub-section's lead-in, and a
proviso or Explanation is its own version. So a chunk spans within one version. Grouping a unit's chunks is
retrieval's collapse (docs/04 §5), and the rule a node qualifies rides in `context_prefix`.
- `nizam/storage/chunking.py` cuts spans of at most 1,200 chars. Within [400, 1,200] it prefers, in order: a sentence
  end (never after 's.', 'No.', 'Rs.'), then ';' or ':', then ',', then a space.
- Chunks exist **only for released versions**. `python -m nizam.workers.chunk --apply` (`./nz chunk`) adds, removes
  and rebuilds stale context. It is post-replay step 4c, and audit A20 asserts the boundary.
- Measured 18 Nov: 1,132,245 chunks over 1,114,427 versions; 9,699 versions are split. The 275 versions with no text
  get none.

**Lexical indexes.** pg_search is pinned at 0.25.6; the migration refuses any other version (docs/04 §4.1).

| index | over | read by |
|---|---|---|
| `ix_provision_version_bm25` | `text_normalised`, stemmed English | `Bm25LexicalSearch.search` |
| `ix_provision_bm25` | `heading`, `marginal_note` (stemmed), `replace(label,' ','')` as a lowercased literal | `.headings`, `.labels` ('462I' finds '462 I') |
| `ix_instrument_bm25` | `short_title`, `display_title`, `long_title` | titles, for retrieval's field boosts |
| `ix_provision_version_fts` | GIN over the `to_tsvector('english', text_normalised)` **expression** | the portable fallback |

Every index covers all rows. `nizam/storage/lexical.py` reads candidates **through `operative_provision`** in two
steps, then a widening window:
1. It takes the index's best window of version ids.
2. It asks the view about exactly those ids. A one-statement join made the planner expand the whole view (27 s).
3. The window widens until k operative candidates are found. Retired revisions repeat operative text: 12 of the top
   80 BM25 matches were operative.

Sizes: body BM25 295 MB, provision BM25 141 MB, titles 4 MB, GIN 93 MB. The chunk table is 299 MB.

### `embedding_generation` and the dense indexes (0109–0113, D-098, D-099)

**`embedding_generation`** says which space `chunk.embedding` lives in. A query is encoded only by the active row's
model, and a replay (INV-3) names it.

| column | |
|---|---|
| `model`, `revision` | hub id and the exact commit of the weights (bge-m3 @ 5617a9f6 today) |
| `dims`, `quantization` | 1024; `binary_sign` (the only value allowed) |
| `pooling`, `query_template` | `cls` / `mean` / `lasttoken`, read from the model's own config; `{q}` or the instruct form the model card requires |
| `passage_source`, `max_tokens`, `chunker`, `chunk_count` | what was embedded: `context_prefix + newline + span text`, 512 tokens, the chunk table's rule and size |
| `selection` | jsonb: the dev-split bake-off numbers, the paired binary-vs-full CI and the encoder validation |
| `active` | one row at most **per encoder device** (partial unique index `uq_embedding_generation_active` on `encoder_device`, 0112; before 0112, one row at most) |
| `encoder_device` | `cpu` \| `gpu` (0112, D-099): where the query encoder runs. `cpu` = bge-m3 int8 ONNX in-process; `gpu` = Qwen3-Embedding-8B on the GPU host (`nizam.inference.remote`) |
| `storage` | `chunk.embedding` for the CPU generation, `chunk_embedding_gpu` for the GPU one (checked against `encoder_device`) |
| `vector_dims`, `rescore_dims` | the model's full output width (1024 / 4096); a stored halfvec prefix that re-ranks the Hamming window, or NULL (NULL today) |

Two generations are active today, each complete over the chunks (A21, A22): **1** BAAI/bge-m3 (cpu, `bit(1024)` in
`chunk.embedding`) and **2** Qwen/Qwen3-Embedding-8B @ 1d8ad4ca (gpu, `bit(4096)` in `chunk_embedding_gpu`). They never
share a column or an index; `Session.generation_for(encoder.info)` picks the space by the encoder's model, commit,
pooling and template, so a query is never compared with another model's passages.

**`chunk_embedding_gpu`** (0113, D-099): the GPU generation's vectors, one row per chunk.

| column | |
|---|---|
| `chunk_id` | PK, `REFERENCES chunk(id) ON DELETE CASCADE`: a replay that removes a chunk removes its vector |
| `generation_id` | the GPU generation that made it |
| `jurisdiction` | copied from `chunk.jurisdiction` by trigger `tr_chunk_embedding_gpu_jurisdiction`, never by hand: the scope filter inside the HNSW scan |
| `bits` | `bit(4096)`: the sign of all 4,096 dimensions, `np.packbits(v > 0)` order. The width was chosen on dev by a rule fixed before any vector existed (D-099); the loader reads it from this type |

- `ix_chunk_embedding_gpu_hnsw`: HNSW `bit_hamming_ops`, m = 16, ef_construction = 64; dropped and rebuilt by the
  loader after a whole load (4 min 54 s, 890 MB; the table is 636 MB).
- `tools/load_embeddings_gpu.py DS_DIR RUN_DIR... --evidence F... [--apply]` loads a whole shard run under a new active
  GPU generation in one transaction (the CPU generation untouched); `--topup DS_DIR RUN_DIR` adds a replay's new
  chunks under the active one. Both refuse unless the shards verify and the chunk ids are exactly the database's.
  With `--apply` a whole load also writes the GPU encoder's reference bundle (`/mnt/e/nizam-data/models/encoder-gpu`).

- `tools/load_embeddings.py RUN_DIR SLUG ENCODER_DIR [--evidence F] [--apply]` writes a Kaggle run's bits under a new
  active generation, in one transaction. It refuses unless the run's chunk ids are exactly today's and the encoder is
  the run's model, commit, pooling and template. Dry run by default.
- **`ix_chunk_hnsw`** (0111): HNSW `bit_hamming_ops`, m = 16, ef_construction = 64, built after the load (3 min 28 s,
  464 MB). `nizam.storage.unit_search.Session.dense_hits` scans a scope of at most `EXACT_SCAN_CHUNKS` (120,000,
  `NIZAM_EXACT_SCAN_CHUNKS`) exactly and uses HNSW elsewhere, with `iterative_scan = strict_order`. Dense scores are
  `1 − hamming/512`.
- The query encoder (int8 ONNX, `nizam.inference.encoder`, `NIZAM_ENCODER_DIR`, default
  `/mnt/e/nizam-data/models/encoder`) is not in the database. `./nz export` copies it with SHA256SUMS, and
  `./nz restore` verifies and installs it.

### `operative_provision` — the view retrieval reads (INV-5)

Migration 0071, redefined by 0075, 0077, 0086, 0093–0100, 0102 and 0103; docs/03b §6.2 as built. Set the date
first: `SET nzq.as_of = 'YYYY-MM-DD'`. A read without it raises. `nzq.territory` is optional and takes
punjab · sindh · kp · balochistan · ict · ajk · gb (0086).

It returns the released provisions whose version is valid at `as_of`. Before capture, a version counts as valid
back to its `text_known_from` (0096–0099). It drops:

- instruments not yet enacted at `as_of`;
- instruments whose established commencement is after `as_of`;
- instruments repealed on or before `as_of`;
- instruments not current or historical from their `not_current_from` (lapsed Ordinances, 0091; replaced or
  superseded laws; pre-1947 archive texts);
- historical expressions whose window misses `as_of`;
- instruments out of the territory, when one is set. Reach comes from the law's own extent clause (0095) or else
  its title. A federal law does not reach AJK or GB, where federal Acts run only as adapted or extended;
- instruments a territorial repeal has removed from that territory (0095, NULL-safe since 0100);
- **units a later law repeals or omits, with everything under them** (0102, `mv_provision_repeal`), from the
  repeal, everywhere or in the repealing province.

It keeps a unit a whole repeal expressly excepts (0103, `mv_provision_survival`), such as Part VIIIA of the
Companies Ordinance, 1984 or s.7(1) of the PIA Corporation (Conversion) Act, 2016. Its last column
`survives_repeal` is true there: the law has gone and this unit has not.

Urdu and Sindhi text is returned in `text_ur` only. Every row carries
`commencement_coverage` (`established` · `not_tracked`),
`invalidation_coverage` (`not_tracked`) and `extent_coverage`
(`jurisdiction_default`). An unknown is declared, never hidden.

**Territories (owner decision, 14 Nov 2026).** ICT, AJK and GB are in scope.
Their sources are `pk-ict`, `pk-ajk` and `pk-gb`, and the segment worker files
them under `ict`, `ajk` and `gb`. It now refuses a source it does not know: it
used to fall back to `fed`, the mislabel docs/02 §2.2 forbids. An
Islamabad-only Act of Parliament stays `fed`, its enacting legislature's number
series. So do the instruments of federal bodies made for Islamabad, such as
CDA regulations and Cabinet Division S.R.O.s: the corpus already held about 25
of these as `fed` (Pakistan Code, DRS), and CDA files land under `pk-federal`.
`ict` is reserved for Islamabad's own local-government instruments; no source
for those has been found yet. **Precondition before any retrieval reads AJK or
GB law.**
The `jurisdiction_default` rule ("federal law plus the territory's own") is
wrong there: a federal Act runs in AJK only as adapted by AJK law, and in GB
only as extended by notification. `nzq_territory()` therefore still refuses
`ajk` and `gb`. With no territory set, the view returns every jurisdiction,
territories included. docs/04 requires a territory or an explicit comparison,
never a guess. The docs/03b §6 `extent` relation must be built before these
territories are served. *(As built, 15–16 Nov: 0086 made reach per instrument. A federal law's reach excludes
AJK and GB, so `nzq_territory()` accepts both, and an AJK or GB read returns only that territory's own law.)*

**GB from archived captures (lead decision, 16 Nov 2026, standing owner
delegation).** docs/02 §3.1 names no archive route, so this records one. GB's
laws are on official hosts the corpus cannot fetch today:

- `gba.gov.pk`, the GB Assembly's site, files its Acts under
  `/tables/alldocuments/actdocx/` and presents an expired TLS certificate.
  TLS is never bypassed.
- `gbassembly.gbit.gov.pk` and `gilgitbaltistan.gov.pk` refuse connections.
  This was probed from two network stacks; Pakistan Code and law.gok.pk
  answered from the same host.

The Internet Archive captured these files from those hosts while they served
them. `tools/acquire/stage_wayback.py` stages them:

1. It asks the CDX index for the host's PDF captures that answered 200.
2. It takes one capture per payload digest.
3. It fetches the raw capture (`/web/<ts>id_/<url>`, the bytes as the host
   served them), with TLS verified.
4. It keeps the bytes **only** when their SHA-1 equals the digest the archive
   recorded at capture time.

The landed observation's `canonical_url` is the **official** URL.
`source_metadata.archived_capture` gives the capture URL, its timestamp and the
verified digest, and `staged_fetch` names the tool. Nothing claims the official
host was fetched today. Everything after staging is the ordinary lane:
preflight, selection (text-layer laws only, the owner's no-OCR rule), landing,
extraction, the Poppler gates and release.

Consolidated text is valid from its 2026 observation date, so a question about
an earlier date finds no text and abstains. The exception is 0064 historical
expressions.

### `segmentation_curation_patch` — auditable source corrections

An append-only, fail-closed correction to parser input, never an edit to
`text_block`. A patch is located by observation, physical page, stable
`match_text`, and exact `before_text`; it applies only when that locator resolves
once. `evidence`, `review_state`, `created_by`, and timestamps preserve the
decision trail. Only `source_verified` and `human_verified` patches are active,
and audit S8 compares their count with the active segmentation run.

### `segmentation_profile_pin` — which parser rules an observation is built with

Migrations 0056-0059. An append-only pin naming the segmentation profile one
source observation is parsed with (`default`, `unreleased-v1`, `unreleased-v2`,
`unreleased-v3` or `unreleased-v4`, a closed list); absent
means `default`, today's parser. `v_segmentation_profile_latest` is the head per
observation, and `nizam.workers.segment.build()` reads it on every build, so a
pinned document replays under the same rules it was released with. The trigger
refuses UPDATE, DELETE, a supersede across observations, and any non-default
pin on an observation that has a released instrument. A tree built under a
profile records its writer as `nizam.corpus.segment/N+<profile>`. Contract:
[SEGMENTATION-PROFILES](SEGMENTATION-PROFILES.md).

### Structural candidates and adjudications — item-level S7 evidence

`segmentation_structural_candidate` stores each parser decision that would
otherwise exist only as an aggregate run counter. A candidate is immutable and
tied to the source observation, active document and instrument revision,
candidate/canonical provisions, exact source blocks, physical pages, printed
label, proposed resolution and parser evidence.

`segmentation_structural_adjudication` is an append-only decision stream. It
records the resolution, whether the basis was machine, source or human evidence,
the method, rationale, evidence payload and optional superseded decision. It
never edits the source block or silently changes the provision tree.

`v_active_structural_candidate` selects candidates belonging to the current,
canonical instrument revision. `v_structural_adjudication_latest` resolves the
decision head, and `v_structural_adjudication_pending` is the exact S7 work
queue. Only `accept_non_citable` resolves the tree as currently written;
restore, reparent, split and reject decisions stay pending until a corrected
revision supersedes that candidate. Audit S7 requires both no pending items and
exact agreement between the active segmenter's aggregate count and item rows.

`instrument_identity_resolution` stores an append-only full-tree SHA-256 proof
for a redundant instrument revision and its canonical peer. The resolver first
requires the same source-blob hash, then compares relative paths, kinds, labels,
headings, ordering, pages, source blocks and every provision text/version field.
It sets `instrument.duplicate_of` only after an exact match. Distinct source
observations and all of their evidence remain queryable.

Expression source variants use a separate, explicitly narrower contract:
`nizam.expression_source_variant/1` in the append-only expression manifest's
`evidence.source_variant_disposition`. This links two reviewed reproductions of
the same issued instrument while retaining known print differences and any
unreadable loci. It does **not** create an0036 equality proof, qualify the copy's
operative text, assert current/historical version equivalence, or substitute
target provision citations. The bounded initial scope is9361 ordinals3–9;
`docs/EXPRESSION-SOURCE-VARIANTS.md` defines the evidence and transaction guards.

`segmentation_boundary_candidate` stores a title/formula/section-reset proposal
when one official PDF appears to contain another independently citable legal
instrument. Every proposal is anchored to the exact block and physical page;
`segmentation_boundary_adjudication` stores append-only review. Confirming a
split does not release the old one-instrument tree: it remains pending until a
new multi-expression materialisation supersedes that tree. Migration 0038 adds
this condition to the application release views.

### Verification, assertion, OCR-candidate and archive evidence

`extraction_verification` stores append-only outputs from independent character,
OCR, word-order and text-plausibility verifiers. `extraction_assertion` and
`instrument_status_assertion` record reviewed exceptions with evidence rather
than weakening global thresholds. `page_ocr_candidate` retains alternative OCR
for review. `revision_archive_batch`, `document_revision_archive_manifest`, and
`instrument_revision_archive_manifest` provide the queryable hash/count receipt
required before superseded derived rows may be pruned.

---

## Views — what you should actually query

| view | why |
|---|---|
| `operative_provision` | **what retrieval reads** (0071): released provisions in force at `nzq.as_of` (required) in `nzq.territory`, with instrument citation facts and coverage flags |
| `v_instrument_metadata_current` | the standing display title, number, dates and text language per expression, resolved to the active instrument (0070) |
| `v_consolidated_twin_current` | as-made Gazette texts linked to the consolidated text of the same law (0075); `operative_provision` serves only the consolidated one |
| `v_amendment_reference_current` | printed amendment footnotes resolved to the amended provision and, where exactly one matches, the amending instrument (0072–0074, abbreviations 0078) |
| `legal_edge` | docs/03b edges as built (0079): `amends` and `repeals` resolved from the source-keyed records to current ids |
| `v_provision` | every provision with its **currently operative** text. **Read this, never `provision_version` directly** — that is INV-5 in practice |
| `v_document` | extracted documents by published title; the join you keep writing by hand |
| `v_provision_source` | the blocks a provision was built from — its trail back to the printed page |
| `v_block_accounting` | per document: is every block placed, and where did its characters go |
| `v_extract_queue` | blobs with no document, and why the last attempt failed |
| `v_instrument_duplicates` | citations claimed by more than one document — the identity-resolution queue (numbered, dated instruments only; 0063) |
| `v_instrument_historical` | active instruments an active manifest declares historical (0064): window, current-expression key, basis and owner decision; the library's `as_of` gate |
| `v_unstructured_document` | documents whose text is stored but is not in the provision tree, with the reason |
| `v_document_quality_status` | newest character, OCR, sequence and language-quality evidence per active document; missing evidence is an explicit failure state |
| `v_release_document`, `v_release_page`, `v_release_text_block` | fail-closed production boundary: only active documents whose newest required evidence all passes |
| `v_active_structural_candidate`, `v_structural_adjudication_latest`, `v_structural_adjudication_pending` | current item-level structural evidence and its unresolved review queue |
| `v_active_boundary_candidate`, `v_boundary_adjudication_latest`, `v_boundary_adjudication_pending` | exact source anchors and review state for possible internal legal-instrument boundaries |
| `v_release_instrument`, `v_release_provision`, `v_release_provision_version` | legal release boundary: quality-passed canonical active revisions with complete printed contents and no pending S7 or multi-instrument boundary |
| `v_toc`, `v_toc_gap` | printed contents with exact source anchors; unresolved entries form a worklist |
| `v_toc_disposition_assertion_latest` | the standing omitted/repealed disposition per printed contents entry; an entry whose latest assertion is withdrawn (0061) has none |
| `v_toc_gap_pending`, `v_toc_gap_source_incomplete` | contents gaps still blocking release; and those released as "not available in this copy" under a standing source-incompleteness record |
| `v_corpus_health`, `v_segmentation_health` | the dashboard rollups |

---

## Enum types in full

```
block_role          body · contents · preface · preamble · heading · footnote
                    running_header · schedule_row · unstructured · unassigned
extraction_lane     E1 · E2 · E3 · E4 · E5
extraction_outcome  extracted · rejected · error
instrument_kind     constitution · act · ordinance · order · regulation · rules
                    sro · notification
jurisdiction        fed · punjab · sindh · kp · balochistan · ict · ajk · gb
lifecycle_state     in_force · repealed · spent · lapsed · not_yet_commenced
observation_outcome landed · failed · missing · skipped · unknown
provision_kind      part · chapter · section · article · subsection · clause
                    proviso · explanation · illustration · schedule · preamble
                    form · appendix · annexure · order · notification
version_op          original · inserted · substituted · omitted · amended
```

---

## Delete behaviour, and why it is what it is

| edge | on delete | reason |
|---|---|---|
| `provision.parent_id` | CASCADE | a subtree without its root is not law |
| `provision.instrument_id` | CASCADE | a derived tree has no meaning without its instrument revision |
| `provision_block.block_id/document_id/provision_id` | CASCADE | a mapping has no meaning without its source block, document or derived provision |
| `provision_block.assignment_set_id` | RESTRICT | evidence revisions are removed only by the restore-tested archive workflow |
| `instrument.document_id` | CASCADE | an instrument is an interpretation of one document |
| `document.supersedes_document_id` | RESTRICT | preserves the extraction revision chain |
| `instrument.supersedes_instrument_id` | RESTRICT | preserves the legal-tree revision chain |
| `provision.first_block` | SET NULL | losing the anchor weakens the evidence trail; it does not delete the law |
| `extraction_attempt.document_id` | SET NULL | **the attempt record outlives the document** — that is the point of a ledger |
| `segmentation_run.instrument_id` | SET NULL | same |
| `instrument.duplicate_of` | SET NULL | a resolution judgement, not a structural edge |

`provision_block` was the one that had to be corrected: `SET NULL` there fought the
CHECK constraint and made every re-segmentation fail. Migration 0008.

---

## Regenerating this

```bash
./nz psql -c '\d+ provision'          # one table
docker compose -f infra/compose.yaml exec -T postgres \
  pg_dump -U nizam -d nizam_clean --schema-only --no-owner --schema=public
```

Schema lives in `infra/postgres/migrations/`, in git, never in a GUI (doc 09a §7).
The current database has 42 applied migrations through
`0041_pgcrypto_evidence_hashes`. Migrations 0037 and 0038 add the
contents-completeness and multi-instrument release gates; 0039 supplies the
foreign-key indexes required by archive-first pruning; 0040 adds guarded,
versioned multi-expression source spans; and 0041 makes source-evidence hashes
available inside PostgreSQL.
Applied migrations are historical facts: 0006, 0007 and 0008 are three files
because the first was wrong twice, and editing it would have erased that. 0009
and 0010 are two files because `ALTER TYPE ... ADD VALUE` must commit before the
new label can be used in a constraint.
