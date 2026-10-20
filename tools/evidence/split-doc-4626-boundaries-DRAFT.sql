-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4626.sh with psql variables, because the document is the
-- OCR-promoted revision of 4626 whose id and block ids exist only after the promotion:
--   ./nz psql -v ON_ERROR_STOP=1 -v doc=<promoted id> -v blk=<E0's first span block> < this file
-- Source-verified boundary evidence for the reviewed split of that revision
-- (tools/evidence/multi-instrument-plans/doc-<promoted id>.json, written from claude/agK6/work/agK6-mkplan_4626.py).
--
-- The PDF (observation 4548) is the Sindh Government Gazette of Thursday 12 March 2020 (No. 12). PDF p1 (gazette 298): the
-- cover and the S&GAD notification of 3 March 2020 amending the Sindh Civil Servants (APT) Rules, 1974 (plan E1; it opens
-- the document at its first block: no boundary row). PDF p2 (gazette 302): the end of an officers' list notification
-- (outside every span), then 'LOCAL GOVERNMENT AND / HOUSING TOWN PLANNING / DEPARTMENT', 'Karachi dated the 20th February
-- 2020', No.RO(LG)/MISC/4(21)/2019 and the Constitution and Regulation of the Sindh Councils Unified Grades (Service) Rules,
-- 2020 (plan E0, the primary expression) to the signature on p12. E0 does not open the document, so its first span block is
-- anchored here. Owner: export m 4626 q1 'split'.
--
-- Guards: the anchor must be the 'LOCAL GOVERNMENT AND' block on PDF page 2 of the promoted revision of 4626, page 2 must
-- print rule 1(1)'s title (the span start checked against the printed title), and an active single-tree instrument must
-- exist (the first segmentation). Idempotent.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k6_args ON COMMIT DROP AS SELECT :doc::bigint AS doc, :blk::bigint AS blk;

DO $$
DECLARE a k6_args%ROWTYPE; heading int; title int;
BEGIN
    SELECT * INTO a FROM k6_args;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = a.doc AND supersedes_document_id = 4626 AND is_active) THEN
        RAISE EXCEPTION 'document % is not the active promoted revision of 4626', a.doc;
    END IF;
    SELECT count(*) INTO heading FROM text_block t
     WHERE t.document_id = a.doc AND t.id = a.blk AND t.page_no = 2 AND t.text LIKE 'LOCAL GOVERNMENT AND%';
    SELECT count(*) INTO title FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 2
       AND t.text LIKE '%These rules may be called the Constitution and Regulation of the Sindh Councils Unified Grades (Service) Rules, 2020%';
    IF heading <> 1 OR title <> 1 THEN
        RAISE EXCEPTION 'block % of % is not the Local Government Department heading on page 2 above the Rules'' title '
            '(heading %, title %)', a.blk, a.doc, heading, title;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = a.doc AND i.source_observation_id = 4548
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document % has no active single-tree instrument (run the first segmentation)', a.doc;
    END IF;
END $$;

WITH args AS (SELECT * FROM k6_args),
active_instrument AS (
  SELECT i.id FROM instrument i, args
   WHERE i.document_id = args.doc AND i.source_observation_id = 4548
     AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT a.id, 4548, args.doc, args.blk, 2,
       'The Constitution and Regulation of the Sindh Councils Unified Grades (Service) Rules, 2020',
       'rules', 2020, NULL, 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'plan', 'tools/evidence/multi-instrument-plans/doc-' || args.doc || '.json',
         'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json',
         'owner_question', jsonb_build_object('document_id', 4626, 'question_id', 'q1', 'choice', 'split'),
         'source_facts', jsonb_build_array(
           'page 1 (gazette 298) carries the cover and the S&GAD notification of 3 March 2020 amending the Sindh Civil Servants (APT) Rules, 1974, to the substituted clause (e)',
           'page 2 (gazette 302) opens inside another notification: an officers'' list 1-12, para 2 and the signature LAEEQ AHMED',
           'then LOCAL GOVERNMENT AND / HOUSING TOWN PLANNING / DEPARTMENT, ''Karachi dated the 20th February 2020'', No.RO(LG)/MISC/4(21)/2019 ''In exercise of the powers conferred by section 138 ... the following rules, namely:-'', PART-I PRELIMINARY and ''1. (1) These rules may be called the Constitution and Regulation of the Sindh Councils Unified Grades (Service) Rules, 2020.'''),
         'reviewed_pages', jsonb_build_array(1, 2),
         'render_artifact', '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4626/images/page-002.png',
         'render_sha256', '3a32ab874861a3fe105c30b3121aabaf82d37b74296b19b23978431c07103f0f')
  FROM active_instrument a CROSS JOIN args
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (PDF p2, the Local Government Department heading) begins the Constitution and '
       'Regulation of the Sindh Councils Unified Grades (Service) Rules, 2020 -- the document''s primary instrument, '
       'printed after the APT amendment notification (p1) and an officers'' list (top of p2) in the Gazette of 12 March '
       '2020 (owner decision export m, 4626 q1 split).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-' || c.document_id || '.json',
                          'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c, k6_args args
 WHERE c.document_id = args.doc AND c.source_observation_id = 4548
   AND c.start_block_id = args.blk
   AND c.method = 'claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id = c.id AND a.resolution = 'confirmed_split');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate c
                     JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
                     JOIN k6_args args ON c.document_id = args.doc AND c.start_block_id = args.blk) THEN
        RAISE EXCEPTION 'no confirmed_split at the Rules'' span start';
    END IF;
END $$;

COMMIT;

SELECT c.id, c.start_block_id, c.source_page, left(c.detected_title, 80) AS title, a.resolution
  FROM segmentation_boundary_candidate c
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id = 4548 AND c.method = 'claude.multi-expression-plan/1';
