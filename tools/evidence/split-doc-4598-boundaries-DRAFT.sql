-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4598.sh with psql variables, because the document is the
-- OCR-promoted revision of 4598 whose id and block ids exist only after the promotion:
--   ./nz psql -v ON_ERROR_STOP=1 -v doc=<promoted id> -v blk=<E1's first span block> < this file
-- Source-verified boundary evidence for the reviewed split of that revision
-- (tools/evidence/multi-instrument-plans/doc-<promoted id>.json, written from claude/agK6/work/agK6-mkplan_4598.py).
--
-- The PDF (observation 4686, 'SINDH LETTERS OF ADMINISTRATION AND SUCCESSION CERTIFICATES RULES, 2020', eight pages)
-- prints on pp1-7 the Gazette of Monday 7 June 2021 (gazette pp420-426): the Law Department's notification
-- NO.S.REG:4(4)/2021/136 making the Rules, rules 1-7, the signature, Schedules I-IV and the imprint; and on p8 a
-- separate Gazette issue, KARACHI FRIDAY JUNE 18, 2021, PART-I, carrying the department's CORRIGENDUM
-- No.S.REG:4(4)/2021 dated 18 June 2021 to the Rules (items (c) and (d)), signed ALI AHMED BALOCH.
-- Owner: decision-review-2026-10-18-4598-4626.json, document 4598, q1 'split'. The Rules open the document at its
-- first block, so they need no boundary row; the corrigendum's span starts at p8's first block, the issue's masthead
-- 'EXTRAORDINARY', and is anchored here.
--
-- Guards: the anchor must be the first block of PDF page 8 of the promoted revision of 4598, an active single-tree
-- instrument must exist (the first segmentation), and page 8 must print the corrigendum's caption and number (the
-- span start checked against the printed title). Idempotent.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k6_args ON COMMIT DROP AS SELECT :doc::bigint AS doc, :blk::bigint AS blk;

DO $$
DECLARE a k6_args%ROWTYPE; first_on_p8 bigint; caption int; number_line int;
BEGIN
    SELECT * INTO a FROM k6_args;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = a.doc AND supersedes_document_id = 4598 AND is_active) THEN
        RAISE EXCEPTION 'document % is not the active promoted revision of 4598', a.doc;
    END IF;
    SELECT t.id INTO first_on_p8 FROM text_block t WHERE t.document_id = a.doc AND t.page_no = 8
     ORDER BY t.reading_order LIMIT 1;
    IF first_on_p8 IS DISTINCT FROM a.blk THEN
        RAISE EXCEPTION 'anchor % is not the first block of page 8 (%)', a.blk, first_on_p8;
    END IF;
    SELECT count(*) INTO caption FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 8 AND btrim(t.text) = 'CORRIGENDUM';
    SELECT count(*) INTO number_line FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 8 AND t.text LIKE 'No.S.REG:4(4)/2021:- In the Sindh Government Gazette%'
       AND t.text LIKE '%Succession Certificates Rules, 2020%';
    IF caption <> 1 OR number_line <> 1 THEN
        RAISE EXCEPTION 'page 8 of % does not print the corrigendum caption and number (caption %, number %)',
            a.doc, caption, number_line;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = a.doc AND i.source_observation_id = 4686
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document % has no active single-tree instrument (run the first segmentation)', a.doc;
    END IF;
END $$;

WITH args AS (SELECT * FROM k6_args),
active_instrument AS (
  SELECT i.id FROM instrument i, args
   WHERE i.document_id = args.doc AND i.source_observation_id = 4686
     AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT a.id, 4686, args.doc, args.blk, 8,
       'Law, Parliamentary Affairs and Criminal Prosecution Service Department Corrigendum No.S.REG:4(4)/2021 dated '
       '18 June 2021 (to the Sindh Letters of Administration and Succession Certificates Rules, 2020)',
       'notification', 2021, 'No.S.REG:4(4)/2021', 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'plan', 'tools/evidence/multi-instrument-plans/doc-' || args.doc || '.json',
         'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-18-4598-4626.json',
         'owner_question', jsonb_build_object('document_id', 4598, 'question_id', 'q1', 'choice', 'split'),
         'source_facts', jsonb_build_array(
           'page 7 ends Schedule IV with item 6 and the imprint ''Karachi: Printed at the Sindh Government Press 07-06-2021''',
           'page 8 opens a new Gazette issue: EXTRAORDINARY / Registered No. M324 / The Sindh Government Gazette / Published by Authority / KARACHI FRIDAY JUNE 18, 2021 / PART-I',
           'then GOVERNMENT OF SINDH / LAW, PARLIAMENTARY AFFAIRS AND CRIMINAL PROSECUTION SERVICE DEPARTMENT, ''Karachi, dated the 18th June, 2021.'', the caption CORRIGENDUM and ''No.S.REG:4(4)/2021:- In the Sindh Government Gazette Extraordinary issue, Registered No.M324, Part-I, published on 7th June, 2021 in the litled Rules "The Sindh Letters of Administration and Succession Certificates Rules, 2020" -''',
           'items (c) ''Hyderabad'' to be read as ''Karachi'' and (d) in rule 1(1) ''2020'' to be read as ''2021'', signed ALI AHMED BALOCH, SECRETARY TO GOVERNMENT OF SINDH; foot line ''L.iv - 230  Ext - I - 58  (477)  Price Rs. 05.00'''),
         'reviewed_pages', jsonb_build_array(7, 8),
         'render_artifact', '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4598/images/page-008.png',
         'render_sha256', '43851bd1b7c9d7ce0228fa55cc32d07d31966fbadd336766ee9b47fb276148ca')
  FROM active_instrument a CROSS JOIN args
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (PDF p8, the masthead of the Gazette of 18 June 2021) begins the Law '
       'Department''s corrigendum No.S.REG:4(4)/2021 to the Sindh Letters of Administration and Succession '
       'Certificates Rules, 2020 -- a separate instrument bound after the Rules (owner decision 2026-10-18, 4598 q1 split; '
       'precedents 1626, 1839).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-' || c.document_id || '.json',
                          'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-18-4598-4626.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c, k6_args args
 WHERE c.document_id = args.doc AND c.source_observation_id = 4686
   AND c.start_block_id = args.blk
   AND c.method = 'claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id = c.id AND a.resolution = 'confirmed_split');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate c
                     JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
                     JOIN k6_args args ON c.document_id = args.doc AND c.start_block_id = args.blk) THEN
        RAISE EXCEPTION 'no confirmed_split at the corrigendum''s span start';
    END IF;
END $$;

COMMIT;

SELECT c.id, c.start_block_id, c.source_page, left(c.detected_title, 80) AS title, a.resolution
  FROM segmentation_boundary_candidate c
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id = 4686 AND c.method = 'claude.multi-expression-plan/1';
