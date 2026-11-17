# Agent context — Nizam-e-Qanoon corpus

*Generated 2026-11-16 22:42 UTC from `nizam_clean`. Regenerate with `./nz context`.*

Every number here is a measurement, not a target. If it looks stale, it is — regenerate rather than trusting it.

### The four rules that make a query correct rather than merely valid

1. **`is_active` on every current-state query.** The corpus is append-only
   (migration 0012). Re-extracting or re-segmenting *retires* the previous
   revision rather than deleting it. A query that reads a base table without
   this counts every generation ever produced — 439,024 of the
   1,636,608 provision rows belong to superseded revisions.

2. **`duplicate_of IS NULL` on `instrument`.** Exact duplicates are *linked*,
   not removed. 655 instruments are marked as duplicates today. Omitting
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
| Active documents | 10,188 |
| Instruments (live, non-duplicate) | 10,339 |
| — of those, release-ready | **10,339** |
| — marked duplicate | 655 |
| Provisions live / retired | 1,197,584 / 439,024 |
| Text blocks (active documents) | 2,249,286 |
| Database size | 4808 MB |

### Known problems right now

| problem | count |
|---|---|
| S7 pending label decisions | 0 |
| S10 multi-instrument boundaries | 0 |
| TOC gaps across active provenance trees (raw) | 525 |
| Canonical TOC gaps pending resolution | 0 |
| Instruments blocked from release | 0 |
| Catalogue entries that never landed a file | 54 |
| Structural adjudications made by machine alone | 4023 |

### Tables


**`acquisition_attempt`** — 220 rows, 160 kB
  
`id bigint, source_observation_id bigint, requested_url text, final_url text, http_status integer, media_type text, byte_length bigint, response_sha256 character, object_key text, outcome text, error text, attempted_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`acquisition_exception`** — 66 rows, 104 kB
  
`id bigint, source_observation_id bigint, reason text, attempts_considered integer, first_attempt_at timestamp with time zone, last_attempt_at timestamp with time zone, observed_error text, evidence jsonb, asserted_by text, asserted_at timestamp with time zone, supersedes_id bigint`
  
FK: source_observation_id → source_observation; supersedes_id → acquisition_exception

**`amendment_reference`** — 15,184 rows, 7192 kB
  
`id bigint, source_observation_id bigint, expression_ordinal smallint, footnote_block_id bigint, entry_ordinal smallint, source_page integer, marker text, footnote_text text, operations ARRAY, cited_text text, cited_title text, cited_kind text, cited_number text, cited_year smallint, cited_section text, effective_from date, target_block_id bigint, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`blob`** — 10,188 rows, 3352 kB
  
One stored PDF, addressed by sha256.
  
`sha256 character, source_id text, object_key text, byte_length bigint, media_type text, first_seen timestamp with time zone, created_at timestamp with time zone`

**`block_assignment_set`** — 12,305 rows, 2968 kB
  
`id uuid, document_id bigint, source_observation_id bigint, instrument_id uuid, segmenter text, is_active boolean, supersedes_set_id uuid, retired_at timestamp with time zone, created_at timestamp with time zone`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation; supersedes_set_id → block_assignment_set

**`citation_abbreviation`** — 2 rows, 32 kB
  
`id bigint, abbreviation text, cited_year smallint, jurisdiction text, pattern text, expands_to text, assertion text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`

**`consolidated_twin`** — 51 rows, 88 kB
  
`id bigint, as_made_observation_id bigint, as_made_expression_ordinal smallint, consolidated_observation_id bigint, consolidated_expression_ordinal smallint, as_made_title text, consolidated_title text, basis text, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: as_made_observation_id → source_observation; consolidated_observation_id → source_observation

**`delegation_record`** — 1,042 rows, 712 kB
  
`id bigint, delegated_observation_id bigint, delegated_expression_ordinal smallint, enabling_observation_id bigint, enabling_expression_ordinal smallint, enabling_section_label text, clause_text text, source_block_id bigint, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: delegated_observation_id → source_observation; enabling_observation_id → source_observation

**`document`** — 11,326 rows, 9784 kB
  
One extraction revision of one PDF. NOT one law -- re-extracting makes a new row and retires the old.
  
⚠️ **Filter:** is_active — without it you count every generation ever produced.
  
`id bigint, sha256 character, language text, publication_role text, page_count integer, char_count bigint, printable_ratio numeric, empty_pages integer, lane USER-DEFINED, extractor text, extractor_config jsonb, pdf_metadata jsonb, extracted_at timestamp with time zone, is_active boolean, supersedes_document_id bigint, retired_at timestamp with time zone, verification_state text`
  
FK: sha256 → blob; supersedes_document_id → document

**`document_revision_archive_manifest`** — 0 rows, 24 kB
  
`batch_id uuid, archived_document_id bigint, retained_document_id bigint, sha256 character, decision text, reason text, archived_record jsonb, archived_verification jsonb, retained_verification jsonb`
  
FK: batch_id → revision_archive_batch; sha256 → blob

**`extraction_assertion`** — 253 rows, 480 kB
  
A human statement about a source page: content confirmed, decode damage, visibility reviewed.
  
⚠️ **Filter:** is_active.
  
`id bigint, sha256 character, page_no integer, kind text, evidence text, detail jsonb, asserted_by text, asserted_at timestamp with time zone, is_active boolean`
  
FK: sha256 → blob

**`extraction_attempt`** — 12,198 rows, 4720 kB
  
`id bigint, sha256 character, extractor text, lane USER-DEFINED, outcome USER-DEFINED, document_id bigint, reason text, detail jsonb, duration_ms integer, attempted_at timestamp with time zone`
  
FK: document_id → document

**`extraction_verification`** — 101,488 rows, 41 MB
  
Evidence from the independent pdftotext cross-check. char_recall and char_precision are COLUMNS, not keys in detail.
  
⚠️ **Filter:** take the newest row per document; it is append-only.
  
`id bigint, document_id bigint, verifier text, reference_extractor text, outcome text, char_recall numeric, char_precision numeric, raw_char_precision numeric, token_recall numeric, problems jsonb, hints jsonb, detail jsonb, verified_at timestamp with time zone`
  
FK: document_id → document

**`heading_mislabel_census`** — 35 rows, 56 kB
  
`id bigint, measured_at timestamp with time zone, measured_by text, detector text, detector_sha256 character, corpus_digest character, scope_provisions bigint, active_instruments integer, detail jsonb`

**`heading_mislabel_finding`** — 243 rows, 192 kB
  
`census_id bigint, provision_id uuid, instrument_id uuid, document_id bigint, short_title text, kind text, label text, first_page integer, tree_heading text, printed_name text, block_excerpt text, finding_class text, similarity numeric, toc_linked boolean`
  
FK: census_id → heading_mislabel_census

**`instrument`** — 12,065 rows, 13 MB
  
One legal instrument: an Act, Ordinance, Rules. The thing a citation names.
  
⚠️ **Filter:** is_active AND duplicate_of IS NULL — duplicate_of links exact copies; counting them doubles your answer.
  
`id uuid, jurisdiction USER-DEFINED, kind USER-DEFINED, number text, year smallint, short_title text, long_title text, preamble text, enacted_on date, commenced_on date, gazette_ref text, status USER-DEFINED, repealed_on date, repealed_by_id uuid, scope text, published boolean, source_sha256 character, document_id bigint, source_url text, extraction_conf real, created_at timestamp with time zone, duplicate_of uuid, source_observation_id bigint, is_active boolean, supersedes_instrument_id uuid, retired_at timestamp with time zone, verification_state text, expression_ordinal smallint, source_start_block_id bigint, source_end_block_id bigint, expression_role text, display_title text, text_language text`
  
FK: document_id → document; duplicate_of → instrument; repealed_by_id → instrument; source_end_block_id → text_block; source_observation_id → source_observation; source_sha256 → blob; source_start_block_id → text_block; supersedes_instrument_id → instrument

**`instrument_expression_manifest`** — 1,119 rows, 3864 kB
  
Versioned, source-block-anchored boundaries for every legal expression materialized from a multi-instrument PDF.
  
⚠️ **Filter:** is_active for the current boundary map; retired rows are preserved evidence.
  
`id uuid, source_observation_id bigint, document_id bigint, expression_ordinal smallint, expression_role text, start_block_id bigint, end_block_id bigint, detected_title text, detected_kind USER-DEFINED, detected_year smallint, detected_number text, review_basis text, method text, evidence jsonb, materialized_instrument_id uuid, is_active boolean, supersedes_manifest_id uuid, retired_at timestamp with time zone, created_at timestamp with time zone, historical_validity daterange, current_source_observation_id bigint, current_expression_ordinal smallint`
  
FK: current_source_observation_id → source_observation; document_id → document; end_block_id → text_block; materialized_instrument_id → instrument; source_observation_id → source_observation; start_block_id → text_block; supersedes_manifest_id → instrument_expression_manifest

**`instrument_expression_span`** — 1,159 rows, 208 kB
  
`id bigint, manifest_id uuid, span_ordinal smallint, start_block_id bigint, end_block_id bigint, created_at timestamp with time zone`
  
FK: end_block_id → text_block; manifest_id → instrument_expression_manifest; start_block_id → text_block

**`instrument_identity_resolution`** — 632 rows, 520 kB
  
`id uuid, duplicate_instrument_id uuid, canonical_instrument_id uuid, source_sha256 character, tree_sha256 character, method text, evidence jsonb, resolved_by text, resolved_at timestamp with time zone`
  
FK: canonical_instrument_id → instrument; duplicate_instrument_id → instrument; source_sha256 → blob

**`instrument_metadata_assertion`** — 57,625 rows, 35 MB
  
`id bigint, source_observation_id bigint, expression_ordinal smallint, field text, value text, assertion text, basis text, source_block_id bigint, source_page integer, quote text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`instrument_revision_archive_manifest`** — 53,454 rows, 215 MB
  
`batch_id uuid, archived_instrument_id uuid, retained_instrument_id uuid, source_observation_id bigint, reason text, archived_record jsonb, archived_run jsonb, retained_run jsonb, derived_counts jsonb`
  
FK: batch_id → revision_archive_batch; source_observation_id → source_observation

**`instrument_source`** — 12,065 rows, 1216 kB
  
`instrument_id uuid, source_observation_id bigint, role text`
  
FK: instrument_id → instrument; source_observation_id → source_observation

**`instrument_status_assertion`** — 0 rows, 24 kB
  
`id bigint, instrument_id uuid, asserted_status USER-DEFINED, source_observation_id bigint, method text, review_state text, evidence jsonb, recorded_at timestamp with time zone`
  
FK: instrument_id → instrument; source_observation_id → source_observation

**`instrument_supersession`** — 374 rows, 304 kB
  
`id bigint, superseded_observation_id bigint, superseded_expression_ordinal smallint, superseding_observation_id bigint, superseding_expression_ordinal smallint, superseded_title text, superseded_year smallint, superseding_title text, superseding_year smallint, matched_key text, basis text, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: superseded_observation_id → source_observation; superseding_observation_id → source_observation

**`instrument_toc_entry`** — 172,284 rows, 78 MB
  
`id bigint, instrument_id uuid, ordinal integer, printed_label text, printed_heading text, printed_page integer, entry_kind text, provision_id uuid, match_method text, source_block_id bigint, source_page integer, source_char_offset integer`
  
FK: instrument_id → instrument; provision_id → provision; source_block_id → text_block

**`page`** — 153,929 rows, 28 MB
  
One page of one document revision.
  
⚠️ **Filter:** join document for is_active.
  
`document_id bigint, page_no integer, width numeric, height numeric, char_count integer, lane USER-DEFINED, crop_box ARRAY, media_box ARRAY`
  
FK: document_id → document

**`page_ocr_adjudication`** — 4,685 rows, 5624 kB
  
A person's decision about which OCR reading the corpus keeps.
  
⚠️ **Filter:** newest row per candidate wins; rejecting never deletes the candidate.
  
`id bigint, candidate_id bigint, decision text, reason text, evidence jsonb, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → page_ocr_candidate

**`page_ocr_candidate`** — 7,995 rows, 33 MB
  
A proposed OCR reading of one page. A proposal, never applied automatically.
  
⚠️ **Filter:** points at the document revision it was made against, which may now be retired.
  
`id bigint, document_id bigint, page_no integer, engine text, languages text, dpi integer, text text, mean_confidence numeric, word_count integer, blocks jsonb, created_at timestamp with time zone, origin_document_id bigint`
  
FK: document_id → page; document_id → document; page_no → page

**`provision`** — 1,637,028 rows, 694 MB
  
A section/subsection in the instrument's tree. INV-4 makes this the citable unit. Text lives in provision_version, not here.
  
⚠️ **Filter:** p.is_active AND join instrument for i.is_active — a provision can be active under a retired instrument.
  
`id uuid, instrument_id uuid, parent_id uuid, path USER-DEFINED, kind USER-DEFINED, label text, heading text, marginal_note text, ordinal integer, first_page integer, last_page integer, first_block bigint, is_active boolean`
  
FK: first_block → text_block; instrument_id → instrument; parent_id → provision

**`provision_ancestor`** — 3,242,934 rows, 739 MB
  
`ancestor_path USER-DEFINED, provision_id uuid, distance smallint`
  
FK: provision_id → provision

**`provision_block`** — 3,219,838 rows, 506 MB
  
`block_id bigint, document_id bigint, provision_id uuid, role USER-DEFINED, chars integer, assignment_set_id uuid`
  
FK: assignment_set_id → block_assignment_set; block_id → text_block; document_id → document; provision_id → provision

**`provision_repeal`** — 0 rows, 96 kB
  
`id bigint, repealed_observation_id bigint, repealed_expression_ordinal smallint, repealed_relative_path text, repealed_unit_as_printed text, repealing_observation_id bigint, repealing_expression_ordinal smallint, repealing_source_block_id bigint, repealing_relative_path text, territory text, clause_text text, verb text, matched_title text, matched_year smallint, repealed_on date, repealed_on_basis text, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: repealed_observation_id → source_observation; repealing_observation_id → source_observation

**`provision_survival`** — 0 rows, 80 kB
  
`id bigint, survived_observation_id bigint, survived_expression_ordinal smallint, survived_relative_path text, subtree boolean, unit_as_printed text, repealing_observation_id bigint, repealing_expression_ordinal smallint, repealing_source_block_id bigint, repealing_relative_path text, clause_text text, matched_title text, matched_year smallint, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: repealing_observation_id → source_observation; survived_observation_id → source_observation

**`provision_version`** — 1,565,725 rows, 1016 MB
  
The text of a provision over time. INV-5: read as at a date.
  
⚠️ **Filter:** bounded by validity; never read the base table for current text.
  
`id uuid, provision_id uuid, validity daterange, text_en text, text_ur text, text_normalised text, operation USER-DEFINED, amended_by_id uuid, amendment_note text, extraction_conf real, verified_by text, verified_at timestamp with time zone, created_at timestamp with time zone, source_toc_disposition_assertion_id bigint`
  
FK: amended_by_id → instrument; provision_id → provision; source_toc_disposition_assertion_id → toc_disposition_assertion

**`revision_archive_batch`** — 6 rows, 32 kB
  
`id uuid, archive_file text, archive_sha256 character, database_size_before bigint, selected_at timestamp with time zone, pruned_at timestamp with time zone, detail jsonb`

**`schema_migration`** — 101 rows, 40 kB
  
`version text, sha256 character, applied_at timestamp with time zone`

**`segmentation_boundary_adjudication`** — 19 rows, 56 kB
  
`id uuid, candidate_id uuid, resolution text, review_basis text, method text, rationale text, evidence jsonb, supersedes_adjudication_id uuid, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → segmentation_boundary_candidate; supersedes_adjudication_id → segmentation_boundary_adjudication

**`segmentation_boundary_candidate`** — 61 rows, 184 kB
  
A detected boundary where one PDF holds several instruments (S10). NOT called multi_instrument_boundary.
  
`id uuid, instrument_id uuid, source_observation_id bigint, document_id bigint, start_block_id bigint, source_page integer, detected_title text, detected_kind text, detected_year integer, detected_number text, confidence numeric, method text, evidence jsonb, created_at timestamp with time zone`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation; start_block_id → text_block

**`segmentation_curation_patch`** — 175,660 rows, 321 MB
  
`id uuid, source_observation_id bigint, operation text, page_no integer, match_text text, before_text text, after_text text, evidence jsonb, review_state text, created_by text, created_at timestamp with time zone, retired_at timestamp with time zone`
  
FK: source_observation_id → source_observation

**`segmentation_profile_pin`** — 1,388 rows, 1528 kB
  
`id bigint, source_observation_id bigint, profile text, reason text, evidence jsonb, pinned_by text, pinned_at timestamp with time zone, supersedes_id bigint`
  
FK: source_observation_id → source_observation; supersedes_id → segmentation_profile_pin

**`segmentation_run`** — 66,597 rows, 41 MB
  
`id bigint, document_id bigint, instrument_id uuid, segmenter text, outcome text, reason text, provisions integer, sections integer, max_depth integer, body_starts_page integer, toc_found boolean, toc_entries integer, toc_matched integer, toc_missing integer, toc_extra integer, toc_agreement numeric, detail jsonb, duration_ms integer, run_at timestamp with time zone, source_observation_id bigint`
  
FK: document_id → document; instrument_id → instrument; source_observation_id → source_observation

**`segmentation_structural_adjudication`** — 4,023 rows, 7936 kB
  
A decision on one structural candidate. Today every row was made by nizam.structural_adjudicator/1 -- a machine, unreviewed.
  
`id uuid, candidate_id uuid, resolution text, review_basis text, method text, rationale text, evidence jsonb, supersedes_adjudication_id uuid, decided_by text, decided_at timestamp with time zone`
  
FK: candidate_id → segmentation_structural_candidate; supersedes_adjudication_id → segmentation_structural_adjudication

**`segmentation_structural_candidate`** — 5,119 rows, 4416 kB
  
A sibling-label collision the segmenter resolved automatically (S7). Its evidence->>'group_size' says how many shared the label.
  
`id uuid, instrument_id uuid, source_observation_id bigint, document_id bigint, candidate_provision_id uuid, canonical_provision_id uuid, parent_provision_id uuid, decision_kind text, original_kind USER-DEFINED, printed_label text, source_block_id bigint, source_page integer, canonical_source_block_id bigint, canonical_source_page integer, proposed_resolution text, segmenter text, evidence jsonb, created_at timestamp with time zone`
  
FK: candidate_provision_id → provision; canonical_provision_id → provision; canonical_source_block_id → text_block; document_id → document; instrument_id → instrument; parent_provision_id → provision; source_block_id → text_block; source_observation_id → source_observation

**`source_incompleteness`** — 54 rows, 264 kB
  
`id bigint, source_observation_id bigint, document_id bigint, resolution text, complete_document_id bigint, body_stops_at text, promised_top text, observed text, attempts_considered integer, first_attempt_at timestamp with time zone, last_attempt_at timestamp with time zone, observed_error text, evidence jsonb, asserted_by text, asserted_at timestamp with time zone, supersedes_id bigint`
  
FK: complete_document_id → document; document_id → document; source_observation_id → source_observation; supersedes_id → source_incompleteness

**`source_non_authoritative_copy`** — 2 rows, 112 kB
  
`id bigint, source_observation_id bigint, document_id bigint, kind text, authoritative_document_id bigint, observed text, owner_decision jsonb, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: authoritative_document_id → document; document_id → document; source_observation_id → source_observation

**`source_observation`** — 10,394 rows, 15 MB
  
One catalogued item from a source portal. outcome='landed' and a sha256 mean the file landed; acquisition_attempt can record a later recovery.
  
⚠️ **Filter:** For unresolved acquisition work, exclude observations with a recovered attempt; a raw sha256-null count includes recovered historical failures.
  
`id bigint, source_id text, canonical_url text, referring_url text, discovered_at timestamp with time zone, fetched_at timestamp with time zone, http_status integer, etag text, last_modified text, media_type text, byte_length bigint, sha256 character, object_key text, scraper_version text, source_metadata jsonb, outcome USER-DEFINED, error_code text, ingested_at timestamp with time zone`

**`source_same_text_copy`** — 6 rows, 136 kB
  
`id bigint, source_observation_id bigint, document_id bigint, canonical_document_id bigint, observed text, owner_decision jsonb, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: canonical_document_id → document; document_id → document; source_observation_id → source_observation

**`statutory_repeal`** — 212 rows, 216 kB
  
`id bigint, repealed_observation_id bigint, repealed_expression_ordinal smallint, repealing_observation_id bigint, repealing_expression_ordinal smallint, repealing_source_block_id bigint, repealing_relative_path text, clause_text text, matched_title text, matched_year smallint, repealed_on date, repealed_on_basis text, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: repealed_observation_id → source_observation; repealing_observation_id → source_observation

**`territorial_repeal`** — 47 rows, 72 kB
  
`id bigint, repealed_observation_id bigint, repealed_expression_ordinal smallint, repealing_observation_id bigint, repealing_expression_ordinal smallint, repealing_source_block_id bigint, repealing_relative_path text, territory text, clause_text text, matched_title text, matched_year smallint, repealed_on date, repealed_on_basis text, assertion text, method text, evidence jsonb, recorded_by text, recorded_at timestamp with time zone`
  
FK: repealed_observation_id → source_observation; repealing_observation_id → source_observation

**`text_block`** — 2,850,138 rows, 822 MB
  
Raw extracted text with page and geometry. The input to segmentation, not a citable unit.
  
⚠️ **Filter:** has NO is_active of its own — join document and filter d.is_active.
  
`id bigint, document_id bigint, page_no integer, block_no integer, reading_order integer, x0 numeric, y0 numeric, x1 numeric, y1 numeric, text text, script text, confidence numeric, inside_cropbox boolean`
  
FK: document_id → page; page_no → page

**`toc_disposition_assertion`** — 289 rows, 368 kB
  
`id bigint, source_observation_id bigint, expression_ordinal smallint, toc_entry_ordinal integer, reviewed_toc_entry_id bigint, printed_label text, printed_heading text, disposition text, source_block_id bigint, source_page integer, render_artifact text, render_sha256 character, amending_instrument_id uuid, amending_instrument_citation text, evidence jsonb, reviewed_by text, reviewed_at timestamp with time zone, supersedes_id bigint`
  
FK: amending_instrument_id → instrument; reviewed_toc_entry_id → instrument_toc_entry; source_block_id → text_block; source_observation_id → source_observation; supersedes_id → toc_disposition_assertion

**`toc_disposition_withdrawal`** — 1 rows, 48 kB
  
`id bigint, assertion_id bigint, reason text, owner_decision jsonb, evidence jsonb, withdrawn_by text, withdrawn_at timestamp with time zone`
  
FK: assertion_id → toc_disposition_assertion

**`toc_gap_adjudication`** — 1,832 rows, 5896 kB
  
`id uuid, instrument_id uuid, document_id bigint, printed_label text, resolution text, source_page integer, evidence jsonb, rationale text, decided_by text, decided_at timestamp with time zone, supersedes_id uuid, toc_entry_id bigint`
  
FK: document_id → document; instrument_id → instrument; supersedes_id → toc_gap_adjudication; toc_entry_id → instrument_toc_entry

### Views — prefer these over base tables

- **`legal_edge`**
- **`operative_provision`** — THE application read of law (INV-5). Requires SET nzq.as_of; optional SET nzq.territory (punjab sindh kp balochistan ict ajk gb). Released law in force on that date and in that territory, with currency and text_known_from.
- **`v_acquisition_exception_latest`**
- **`v_acquisition_unresolved`**
- **`v_active_boundary_candidate`**
- **`v_active_instrument_expression_span`**
- **`v_active_structural_candidate`**
- **`v_amendment_reference_current`**
- **`v_block_accounting`**
- **`v_boundary_adjudication_latest`**
- **`v_boundary_adjudication_pending`** — S10 multi-instrument boundaries not yet decided.
- **`v_citation_abbreviation_current`**
- **`v_consolidated_twin_current`**
- **`v_corpus_health`**
- **`v_delegation_current`**
- **`v_document`**
- **`v_document_quality_status`** — Per-document verdict from every quality verifier.
- **`v_extract_queue`**
- **`v_heading_mislabel_census_current`**
- **`v_heading_mislabel_corpus_state`**
- **`v_instrument_currency`** — Per law: current / not_current / historical, with reason and territory_exits.
- **`v_instrument_duplicates`**
- **`v_instrument_historical`**
- **`v_instrument_metadata_current`**
- **`v_instrument_supersession_current`**
- **`v_ocr_adjudication_evidence`** — Stored text beside a proposed OCR reading, per page.
- **`v_ocr_adjudication_queue`**
- **`v_page_ocr_candidate_review`**
- **`v_provision`**
- **`v_provision_repeal_current`**
- **`v_provision_source`**
- **`v_provision_survival_current`**
- **`v_release_document`**
- **`v_release_instrument`** — Instruments that pass every release gate. THE set an app may serve.
- **`v_release_page`**
- **`v_release_provision`** — Provisions under release-ready instruments.
- **`v_release_provision_version`** — Version text under release-ready provisions; retrieval indexes this view.
- **`v_release_text_block`**
- **`v_segmentation_health`**
- **`v_segmentation_profile_latest`**
- **`v_source_incompleteness_latest`**
- **`v_source_incompleteness_open`**
- **`v_statutory_repeal_current`**
- **`v_structural_adjudication_latest`**
- **`v_structural_adjudication_pending`** — S7 work not yet decided.
- **`v_territorial_repeal_current`**
- **`v_toc`** — Printed contents entries with their source anchors.
- **`v_toc_disposition_assertion_latest`**
- **`v_toc_gap`** — Documents whose printed contents list a section the body lacks.
- **`v_toc_gap_adjudication_latest`**
- **`v_toc_gap_pending`**
- **`v_toc_gap_review_basis`**
- **`v_toc_gap_source_incomplete`**
- **`v_unstructured_document`**

### Enums (these are the only valid values)

- **`block_role`**: body · contents · preface · preamble · heading · footnote · running_header · schedule_row · unassigned · unstructured
- **`edge_kind`**: contains · amends · repeals · saves · commences · empowers · defines · defaults_from · notwithstanding · subject_to · refers_to · interpreted_by · invalidated_by · attracts
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
