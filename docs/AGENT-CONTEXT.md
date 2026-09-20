# Agent context — Nizam-e-Qanoon corpus

*Generated 2026-09-15 14:48 UTC from `nizam_clean`. Regenerate with `./nz context`.*

Every number here is a measurement, not a target. If it looks stale, it is — regenerate rather than trusting it.

### The four rules that make a query correct rather than merely valid

1. **`is_active` on every current-state query.** The corpus is append-only
   (migration 0012). Re-extracting or re-segmenting *retires* the previous
   revision rather than deleting it. A query that reads a base table without
   this counts every generation ever produced — 493,759 of the
   1,027,378 provision rows belong to superseded revisions.

2. **`duplicate_of IS NULL` on `instrument`.** Exact duplicates are *linked*,
   not removed. 146 instruments are marked as duplicates today. Omitting
   this silently doubles counts — it is how a search for theft sections
   returned every section twice.

3. **`text_block` and `page` have no `is_active` of their own.** The flag lives
   on `document`. Join it. This is the single easiest way to get a plausible
   wrong number out of this database.

4. **Text is not on `provision`.** `provision` carries structure (label, path,
   heading); the words live in `provision_version`, bounded by validity, because
   INV-5 answers law as at a date.


### Where the corpus stands

| | |
|---|---|
| Active documents | 4,597 |
| Instruments (live, non-duplicate) | 4,688 |
| — of those, release-ready | **4,198** |
| — marked duplicate | 146 |
| Provisions live / retired | 533,619 / 493,759 |
| Text blocks (active documents) | 955,357 |
| Database size | 2702 MB |

### Known problems right now

| problem | count |
|---|---|
| S7 pending label decisions | 885 |
| S10 multi-instrument boundaries | 0 |
| TOC gaps across active provenance trees (raw) | 1184 |
| Canonical TOC gaps pending resolution | 935 |
| Instruments blocked from release | 490 |
| Catalogue entries that never landed a file | 33 |
| Structural adjudications made by machine alone | 9055 |

### Tables


**`acquisition_attempt`** — 82 rows, 144 kB
  
`id bigint, source_observation_id bigint, requested_url text, final_url text, http_status integer, media_type text, byte_length bigint, response_sha256 character, object_key text, outcome text, error text, attempted_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`acquisition_exception`** — 0 rows, 96 kB
  
`id bigint, source_observation_id bigint, reason text, attempts_considered integer, first_attempt_at timestamp with time zone, last_attempt_at timestamp with time zone, observed_error text, evidence jsonb, asserted_by text, asserted_at timestamp with time zone, supersedes_id bigint`
  
FK: source_observation_id → source_observation; supersedes_id → acquisition_exception

**`blob`** — 4,595 rows, 1696 kB
  
One stored PDF, addressed by sha256.
  
`sha256 character, source_id text, object_key text, byte_length bigint, media_type text, first_seen timestamp with time zone, created_at timestamp with time zone`

**`block_assignment_set`** — 6,587 rows, 2056 kB
  
`id uuid, document_id bigint, source_observation_id bigint, instrument_id uuid, segmenter text, is_active boolean, supersedes_set_id uuid, retired_at timestamp with time zone, created_at timestamp with time zone`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation; supersedes_set_id → block_assignment_set

**`document`** — 4,632 rows, 7976 kB
  
One extraction revision of one PDF. NOT one law -- re-extracting makes a new row and retires the old.
  
⚠️ **Filter:** is_active — without it you count every generation ever produced.
  
`id bigint, sha256 character, language text, publication_role text, page_count integer, char_count bigint, printable_ratio numeric, empty_pages integer, lane USER-DEFINED, extractor text, extractor_config jsonb, pdf_metadata jsonb, extracted_at timestamp with time zone, is_active boolean, supersedes_document_id bigint, retired_at timestamp with time zone, verification_state text`
  
FK: sha256 → blob; supersedes_document_id → document

**`document_revision_archive_manifest`** — 0 rows, 24 kB
  
`batch_id uuid, archived_document_id bigint, retained_document_id bigint, sha256 character, decision text, reason text, archived_record jsonb, archived_verification jsonb, retained_verification jsonb`
  
FK: batch_id → revision_archive_batch; sha256 → blob

**`extraction_assertion`** — 16 rows, 88 kB
  
A human statement about a source page: content confirmed, decode damage, visibility reviewed.
  
⚠️ **Filter:** is_active.
  
`id bigint, sha256 character, page_no integer, kind text, evidence text, detail jsonb, asserted_by text, asserted_at timestamp with time zone, is_active boolean`
  
FK: sha256 → blob

**`extraction_attempt`** — 4,724 rows, 1944 kB
  
`id bigint, sha256 character, extractor text, lane USER-DEFINED, outcome USER-DEFINED, document_id bigint, reason text, detail jsonb, duration_ms integer, attempted_at timestamp with time zone`
  
FK: document_id → document

**`extraction_verification`** — 72,824 rows, 32 MB
  
Evidence from the independent pdftotext cross-check. char_recall and char_precision are COLUMNS, not keys in detail.
  
⚠️ **Filter:** take the newest row per document; it is append-only.
  
`id bigint, document_id bigint, verifier text, reference_extractor text, outcome text, char_recall numeric, char_precision numeric, raw_char_precision numeric, token_recall numeric, problems jsonb, hints jsonb, detail jsonb, verified_at timestamp with time zone`
  
FK: document_id → document

**`instrument`** — 6,553 rows, 11 MB
  
One legal instrument: an Act, Ordinance, Rules. The thing a citation names.
  
⚠️ **Filter:** is_active AND duplicate_of IS NULL — duplicate_of links exact copies; counting them doubles your answer.
  
`id uuid, jurisdiction USER-DEFINED, kind USER-DEFINED, number text, year smallint, short_title text, long_title text, preamble text, enacted_on date, commenced_on date, gazette_ref text, status USER-DEFINED, repealed_on date, repealed_by_id uuid, scope text, published boolean, source_sha256 character, document_id bigint, source_url text, extraction_conf real, created_at timestamp with time zone, duplicate_of uuid, source_observation_id bigint, is_active boolean, supersedes_instrument_id uuid, retired_at timestamp with time zone, verification_state text, expression_ordinal smallint, source_start_block_id bigint, source_end_block_id bigint, expression_role text`
  
FK: document_id → document; duplicate_of → instrument; repealed_by_id → instrument; source_end_block_id → text_block; source_observation_id → source_observation; source_sha256 → blob; source_start_block_id → text_block; supersedes_instrument_id → instrument

**`instrument_expression_manifest`** — 142 rows, 440 kB
  
Versioned, source-block-anchored boundaries for every legal expression materialized from a multi-instrument PDF.
  
⚠️ **Filter:** is_active for the current boundary map; retired rows are preserved evidence.
  
`id uuid, source_observation_id bigint, document_id bigint, expression_ordinal smallint, expression_role text, start_block_id bigint, end_block_id bigint, detected_title text, detected_kind USER-DEFINED, detected_year smallint, detected_number text, review_basis text, method text, evidence jsonb, materialized_instrument_id uuid, is_active boolean, supersedes_manifest_id uuid, retired_at timestamp with time zone, created_at timestamp with time zone`
  
FK: document_id → document; end_block_id → text_block; materialized_instrument_id → instrument; source_observation_id → source_observation; start_block_id → text_block; supersedes_manifest_id → instrument_expression_manifest

**`instrument_expression_span`** — 144 rows, 72 kB
  
`id bigint, manifest_id uuid, span_ordinal smallint, start_block_id bigint, end_block_id bigint, created_at timestamp with time zone`
  
FK: end_block_id → text_block; manifest_id → instrument_expression_manifest; start_block_id → text_block

**`instrument_identity_resolution`** — 110 rows, 184 kB
  
`id uuid, duplicate_instrument_id uuid, canonical_instrument_id uuid, source_sha256 character, tree_sha256 character, method text, evidence jsonb, resolved_by text, resolved_at timestamp with time zone`
  
FK: canonical_instrument_id → instrument; duplicate_instrument_id → instrument; source_sha256 → blob

**`instrument_revision_archive_manifest`** — 15,989 rows, 60 MB
  
`batch_id uuid, archived_instrument_id uuid, retained_instrument_id uuid, source_observation_id bigint, reason text, archived_record jsonb, archived_run jsonb, retained_run jsonb, derived_counts jsonb`
  
FK: batch_id → revision_archive_batch; source_observation_id → source_observation

**`instrument_source`** — 5,977 rows, 824 kB
  
`instrument_id uuid, source_observation_id bigint, role text`
  
FK: instrument_id → instrument; source_observation_id → source_observation

**`instrument_status_assertion`** — 0 rows, 24 kB
  
`id bigint, instrument_id uuid, asserted_status USER-DEFINED, source_observation_id bigint, method text, review_state text, evidence jsonb, recorded_at timestamp with time zone`
  
FK: instrument_id → instrument; source_observation_id → source_observation

**`instrument_toc_entry`** — 157,455 rows, 83 MB
  
`id bigint, instrument_id uuid, ordinal integer, printed_label text, printed_heading text, printed_page integer, entry_kind text, provision_id uuid, match_method text, source_block_id bigint, source_page integer`
  
FK: instrument_id → instrument; provision_id → provision; source_block_id → text_block

**`page`** — 63,868 rows, 13 MB
  
One page of one document revision.
  
⚠️ **Filter:** join document for is_active.
  
`document_id bigint, page_no integer, width numeric, height numeric, char_count integer, lane USER-DEFINED, crop_box ARRAY, media_box ARRAY`
  
FK: document_id → document

**`page_ocr_adjudication`** — 144 rows, 200 kB
  
A person's decision about which OCR reading the corpus keeps.
  
⚠️ **Filter:** newest row per candidate wins; rejecting never deletes the candidate.
  
`id bigint, candidate_id bigint, decision text, reason text, evidence jsonb, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → page_ocr_candidate

**`page_ocr_candidate`** — 397 rows, 1352 kB
  
A proposed OCR reading of one page. A proposal, never applied automatically.
  
⚠️ **Filter:** points at the document revision it was made against, which may now be retired.
  
`id bigint, document_id bigint, page_no integer, engine text, languages text, dpi integer, text text, mean_confidence numeric, word_count integer, blocks jsonb, created_at timestamp with time zone, origin_document_id bigint`
  
FK: document_id → page; document_id → document; page_no → page

**`provision`** — 1,006,727 rows, 639 MB
  
A section/subsection in the instrument's tree. INV-4 makes this the citable unit. Text lives in provision_version, not here.
  
⚠️ **Filter:** p.is_active AND join instrument for i.is_active — a provision can be active under a retired instrument.
  
`id uuid, instrument_id uuid, parent_id uuid, path USER-DEFINED, kind USER-DEFINED, label text, heading text, marginal_note text, ordinal integer, first_page integer, last_page integer, first_block bigint, is_active boolean`
  
FK: first_block → text_block; instrument_id → instrument; parent_id → provision

**`provision_ancestor`** — 1,307,719 rows, 495 MB
  
`ancestor_path USER-DEFINED, provision_id uuid, distance smallint`
  
FK: provision_id → provision

**`provision_block`** — 1,906,184 rows, 348 MB
  
`block_id bigint, document_id bigint, provision_id uuid, role USER-DEFINED, chars integer, assignment_set_id uuid`
  
FK: assignment_set_id → block_assignment_set; block_id → text_block; document_id → document; provision_id → provision

**`provision_version`** — 936,006 rows, 644 MB
  
The text of a provision over time. INV-5: read as at a date.
  
⚠️ **Filter:** bounded by validity; never read the base table for current text.
  
`id uuid, provision_id uuid, validity daterange, text_en text, text_ur text, text_normalised text, operation USER-DEFINED, amended_by_id uuid, amendment_note text, extraction_conf real, verified_by text, verified_at timestamp with time zone, created_at timestamp with time zone, source_toc_disposition_assertion_id bigint`
  
FK: amended_by_id → instrument; provision_id → provision; source_toc_disposition_assertion_id → toc_disposition_assertion

**`revision_archive_batch`** — 4 rows, 64 kB
  
`id uuid, archive_file text, archive_sha256 character, database_size_before bigint, selected_at timestamp with time zone, pruned_at timestamp with time zone, detail jsonb`

**`schema_migration`** — 42 rows, 64 kB
  
`version text, sha256 character, applied_at timestamp with time zone`

**`segmentation_boundary_adjudication`** — 0 rows, 64 kB
  
`id uuid, candidate_id uuid, resolution text, review_basis text, method text, rationale text, evidence jsonb, supersedes_adjudication_id uuid, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → segmentation_boundary_candidate; supersedes_adjudication_id → segmentation_boundary_adjudication

**`segmentation_boundary_candidate`** — 42 rows, 328 kB
  
A detected boundary where one PDF holds several instruments (S10). NOT called multi_instrument_boundary.
  
`id uuid, instrument_id uuid, source_observation_id bigint, document_id bigint, start_block_id bigint, source_page integer, detected_title text, detected_kind text, detected_year integer, detected_number text, confidence numeric, method text, evidence jsonb, created_at timestamp with time zone`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation; start_block_id → text_block

**`segmentation_curation_patch`** — 5 rows, 96 kB
  
`id uuid, source_observation_id bigint, operation text, page_no integer, match_text text, before_text text, after_text text, evidence jsonb, review_state text, created_by text, created_at timestamp with time zone, retired_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`segmentation_run`** — 20,941 rows, 11 MB
  
`id bigint, document_id bigint, instrument_id uuid, segmenter text, outcome text, reason text, provisions integer, sections integer, max_depth integer, body_starts_page integer, toc_found boolean, toc_entries integer, toc_matched integer, toc_missing integer, toc_extra integer, toc_agreement numeric, detail jsonb, duration_ms integer, run_at timestamp with time zone, source_observation_id bigint`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation

**`segmentation_structural_adjudication`** — 8,467 rows, 15 MB
  
A decision on one structural candidate. Today every row was made by nizam.structural_adjudicator/1 -- a machine, unreviewed.
  
`id uuid, candidate_id uuid, resolution text, review_basis text, method text, rationale text, evidence jsonb, supersedes_adjudication_id uuid, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → segmentation_structural_candidate; supersedes_adjudication_id → segmentation_structural_adjudication

**`segmentation_structural_candidate`** — 12,973 rows, 11 MB
  
A sibling-label collision the segmenter resolved automatically (S7). Its evidence->>'group_size' says how many shared the label.
  
`id uuid, instrument_id uuid, source_observation_id bigint, document_id bigint, candidate_provision_id uuid, canonical_provision_id uuid, parent_provision_id uuid, decision_kind text, original_kind USER-DEFINED, printed_label text, source_block_id bigint, source_page integer, canonical_source_block_id bigint, canonical_source_page integer, proposed_resolution text, segmenter text, evidence jsonb, created_at timestamp with time zone`
  
FK: candidate_provision_id → provision; canonical_provision_id → provision; canonical_source_block_id → text_block; document_id → document; instrument_id → instrument; parent_provision_id → provision; source_block_id → text_block; source_observation_id → source_observation

**`source_observation`** — 4,763 rows, 8360 kB
  
One catalogued item from a source portal. outcome='landed' and a sha256 mean the file landed; acquisition_attempt can record a later recovery.
  
⚠️ **Filter:** For unresolved acquisition work, exclude observations with a recovered attempt; a raw sha256-null count includes recovered historical failures.
  
`id bigint, source_id text, canonical_url text, referring_url text, discovered_at timestamp with time zone, fetched_at timestamp with time zone, http_status integer, etag text, last_modified text, media_type text, byte_length bigint, sha256 character, object_key text, scraper_version text, source_metadata jsonb, outcome USER-DEFINED, error_code text, ingested_at timestamp with time zone`

**`text_block`** — 968,951 rows, 302 MB
  
Raw extracted text with page and geometry. The input to segmentation, not a citable unit.
  
⚠️ **Filter:** has NO is_active of its own — join document and filter d.is_active.
  
`id bigint, document_id bigint, page_no integer, block_no integer, reading_order integer, x0 numeric, y0 numeric, x1 numeric, y1 numeric, text text, script text, confidence numeric, inside_cropbox boolean`
  
FK: document_id → page; page_no → page

**`toc_disposition_assertion`** — 162 rows, 256 kB
  
`id bigint, source_observation_id bigint, expression_ordinal smallint, toc_entry_ordinal integer, reviewed_toc_entry_id bigint, printed_label text, printed_heading text, disposition text, source_block_id bigint, source_page integer, render_artifact text, render_sha256 character, amending_instrument_id uuid, amending_instrument_citation text, evidence jsonb, reviewed_by text, reviewed_at timestamp with time zone, supersedes_id bigint`
  
FK: amending_instrument_id → instrument; reviewed_toc_entry_id → instrument_toc_entry; source_block_id → text_block; source_observation_id → source_observation; supersedes_id → toc_disposition_assertion

**`toc_gap_adjudication`** — 395 rows, 928 kB
  
`id uuid, instrument_id uuid, document_id bigint, printed_label text, resolution text, source_page integer, evidence jsonb, rationale text, decided_by text, decided_at timestamp with time zone, supersedes_id uuid, toc_entry_id bigint`
  
FK: document_id → document; instrument_id → instrument; supersedes_id → toc_gap_adjudication; toc_entry_id → instrument_toc_entry

### Views — prefer these over base tables

- **`v_acquisition_exception_latest`**
- **`v_acquisition_unresolved`**
- **`v_active_boundary_candidate`**
- **`v_active_instrument_expression_span`**
- **`v_active_structural_candidate`**
- **`v_block_accounting`**
- **`v_boundary_adjudication_latest`**
- **`v_boundary_adjudication_pending`** — S10 multi-instrument boundaries not yet decided.
- **`v_corpus_health`**
- **`v_document`**
- **`v_document_quality_status`** — Per-document verdict from every quality verifier.
- **`v_extract_queue`**
- **`v_instrument_duplicates`**
- **`v_ocr_adjudication_evidence`** — Stored text beside a proposed OCR reading, per page.
- **`v_ocr_adjudication_queue`**
- **`v_page_ocr_candidate_review`**
- **`v_provision`**
- **`v_provision_source`**
- **`v_release_document`**
- **`v_release_instrument`** — Instruments that pass every release gate. THE set an app may serve.
- **`v_release_page`**
- **`v_release_provision`** — Provisions under release-ready instruments.
- **`v_release_provision_version`** — Version text under release-ready provisions; retrieval indexes this view.
- **`v_release_text_block`**
- **`v_segmentation_health`**
- **`v_structural_adjudication_latest`**
- **`v_structural_adjudication_pending`** — S7 work not yet decided.
- **`v_toc`** — Printed contents entries with their source anchors.
- **`v_toc_disposition_assertion_latest`**
- **`v_toc_gap`** — Documents whose printed contents list a section the body lacks.
- **`v_toc_gap_adjudication_latest`**
- **`v_toc_gap_pending`**
- **`v_toc_gap_review_basis`**
- **`v_unstructured_document`**

### Enums (these are the only valid values)

- **`block_role`**: body · contents · preface · preamble · heading · footnote · running_header · schedule_row · unassigned · unstructured
- **`extraction_lane`**: E1 · E2 · E3 · E4 · E5
- **`extraction_outcome`**: extracted · rejected · error
- **`instrument_kind`**: constitution · act · ordinance · order · regulation · rules · sro · notification
- **`jurisdiction`**: fed · punjab · sindh · kp · balochistan · ict · ajk · gb
- **`lifecycle_state`**: unknown · in_force · repealed · spent · lapsed · not_yet_commenced
- **`observation_outcome`**: landed · failed · missing · skipped · unknown
- **`provision_kind`**: part · chapter · section · article · subsection · clause · proviso · explanation · illustration · schedule · preamble · form · appendix · annexure · order
- **`version_op`**: original · inserted · substituted · omitted · amended

### Where things are decided

| topic | document |
|---|---|
| Layers, domain model, ADRs | `docs/01-master-architecture` |
| Extraction, segmentation, quality gates | `docs/02-corpus-and-ingestion` |
| Schema, indexes, publish transaction | `docs/03-data-and-storage` |
| Legal graph: 14 edge types, 9 facets | `docs/03b-legal-data-model` |
| Retrieval and the gate | `docs/04-retrieval` |
| The 30 audit criteria | `tools/audit/criteria.sql` |
