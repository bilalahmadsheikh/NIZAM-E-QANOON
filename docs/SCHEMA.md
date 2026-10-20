# The database as it exists

Dumped from the running cluster, not from the migrations. Everything below was
read out of `pg_catalog` — if a column is here, it is in the database.

PostgreSQL 17 (ParadeDB image) · schema `public` · 32 tables, 27 views, 9 enum types.

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
| `duplicate_of` | uuid | → `instrument`; NULL means *not yet assessed*, **not** "not a duplicate". Set by exact-tree identity (0036), partial-copy supersession (0054) and same-text copies (0062), the last two re-derived after every replay |
| `gazette_ref`, `source_url`, `source_sha256`, `scope`, `extraction_conf`, `published` | | |
| `source_observation_id` | bigint | → the official portal observation interpreted by this revision |
| `expression_ordinal`, `expression_role` | smallint, text | stable expression number; `primary` or `embedded` |
| `source_start_block_id`, `source_end_block_id` | bigint | inclusive source span, guarded to this document and reading order |
| `is_active`, `retired_at` | boolean, timestamptz | active revision selector |
| `supersedes_instrument_id` | uuid | → prior `instrument`, append-only revision chain |
| `verification_state` | text | unverified · passed · review · rejected |

`CHECK ck_repeal`: `status = 'repealed'` **iff** `repealed_on IS NOT NULL`.

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
| `kind` | `provision_kind` | part · chapter · section · article · subsection · clause · proviso · explanation · illustration · schedule · preamble · form · appendix · annexure · order |
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
provision-based subtree query. The active closure is now 1,208,678 rows covering
all 512,094 provisions; audit S9 recursively derives the expected graph and
requires zero missing, extra, or stale rows.

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
right file is landed.

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
                    form · appendix · annexure · order
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
