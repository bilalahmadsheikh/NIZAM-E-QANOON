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
`segmentation_structural_candidate`, `segmentation_structural_adjudication`,
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
| `number`, `year` | text, smallint | year 1800–2100 |
| `short_title`, `long_title`, `preamble` | text | |
| `enacted_on`, `commenced_on`, `repealed_on` | date | |
| `status` | `lifecycle_state` | in_force · repealed · spent · lapsed · not_yet_commenced |
| `repealed_by_id` | uuid | → `instrument` |
| `duplicate_of` | uuid | → `instrument`; NULL means *not yet assessed*, **not** "not a duplicate" |
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
Current state: 131 active manifests across 11 official observations and 11
retired predecessor manifests.

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

### `segmentation_curation_patch` — auditable source corrections

An append-only, fail-closed correction to parser input, never an edit to
`text_block`. A patch is located by observation, physical page, stable
`match_text`, and exact `before_text`; it applies only when that locator resolves
once. `evidence`, `review_state`, `created_by`, and timestamps preserve the
decision trail. Only `source_verified` and `human_verified` patches are active,
and audit S8 compares their count with the active segmentation run.

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
| `v_instrument_duplicates` | citations claimed by more than one document — the identity-resolution queue |
| `v_unstructured_document` | documents whose text is stored but is not in the provision tree, with the reason |
| `v_document_quality_status` | newest character, OCR, sequence and language-quality evidence per active document; missing evidence is an explicit failure state |
| `v_release_document`, `v_release_page`, `v_release_text_block` | fail-closed production boundary: only active documents whose newest required evidence all passes |
| `v_active_structural_candidate`, `v_structural_adjudication_latest`, `v_structural_adjudication_pending` | current item-level structural evidence and its unresolved review queue |
| `v_active_boundary_candidate`, `v_boundary_adjudication_latest`, `v_boundary_adjudication_pending` | exact source anchors and review state for possible internal legal-instrument boundaries |
| `v_release_instrument`, `v_release_provision`, `v_release_provision_version` | legal release boundary: quality-passed canonical active revisions with complete printed contents and no pending S7 or multi-instrument boundary |
| `v_toc`, `v_toc_gap` | printed contents with exact source anchors; unresolved entries form a worklist |
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
