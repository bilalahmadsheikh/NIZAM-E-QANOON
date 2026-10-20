-- DRAFT by agent K6 (19 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4602.sh with psql variables, because the document is the
-- OCR-promoted revision of 4602 (4700) whose block ids exist only after the promotion:
--   ./nz psql -v ON_ERROR_STOP=1 -v doc=<promoted id> -v blk=<E1's first span block> < this file
-- Source-verified boundary evidence for the reviewed split of that revision
-- (tools/evidence/multi-instrument-plans/doc-<promoted id>.json, written from claude/agK6/work/agK6-mkplan_4602.py).
--
-- The PDF (observation 4747, 'SINDH WORKERS WELFARE BOARD EMPLOYEES (SERVICE) RULES, 2021', 71 pages) prints on pp1-70
-- the Gazette Extraordinary of Friday 18 June 2021 (gazette pp526-595): the Labour & Human Resources Department's
-- notification No.L-II-2-39/2020 making the Rules, Chapters I-19 (rules 1-213), the signature, Appendices 1-6 and the
-- (cut-off) imprint; and on p71 a separate Gazette issue, KARACHI TUESDAY JULY 13, 2021, PART-I, carrying the Law,
-- Parliamentary Affairs & Criminal Prosecution Service Department's CORRIGENDUM No.S.REG:4(47)/2020/165(A), dated 1 July
-- 2021, to the Rules' Appendix-2 (Part-III), signed ALI AHMED BALOCH. Read on the render (agent K6, 19 Oct 2026):
-- .artifacts/ocr-review-pack-owner-2026-10-17/doc-4602/images/page-071.png (20a5da9a...): the masthead EXTRAORDINARY /
-- Registered No. M324 / The Sindh Government Gazette / Published by Authority / KARACHI TUESDAY JULY 13, 2021 / PART-I,
-- the department heading, 'Karachi, dated the 1st July,2021.', the printed caption CORRIGENDUM and the number line.
-- Owner: decision-review-2026-10-19-4602.json, q1 'split' ("Split it off, as with 4598"); transcribed for the promoted
-- id as decision-review-2026-10-19-4700.json. The Rules open the document at its first block, so they need no boundary
-- row; the corrigendum's span starts at p71's first block, its issue's masthead 'EXTRAORDINARY' (as 4598's p8), and is
-- anchored here; the anchor is checked against the corrigendum's printed caption and number on the same page.
--
-- Guards: the anchor must be the first block of PDF page 71 of the promoted revision of 4602, page 71 must print the
-- caption CORRIGENDUM and its number line naming the Rules (the span start checked against the printed heading), and an
-- active single-tree instrument must exist (the first segmentation). Idempotent.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k6_args ON COMMIT DROP AS SELECT :doc::bigint AS doc, :blk::bigint AS blk;

DO $$
DECLARE a k6_args%ROWTYPE; first_on_p71 bigint; caption int; number_line int; masthead int;
BEGIN
    SELECT * INTO a FROM k6_args;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = a.doc AND supersedes_document_id = 4602 AND is_active) THEN
        RAISE EXCEPTION 'document % is not the active promoted revision of 4602', a.doc;
    END IF;
    SELECT t.id INTO first_on_p71 FROM text_block t WHERE t.document_id = a.doc AND t.page_no = 71
     ORDER BY t.reading_order LIMIT 1;
    IF first_on_p71 IS DISTINCT FROM a.blk THEN
        RAISE EXCEPTION 'anchor % is not the first block of page 71 (%)', a.blk, first_on_p71;
    END IF;
    SELECT count(*) INTO masthead FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 71 AND btrim(t.text) = 'KARACHI TUESDAY JULY 13, 2021';
    SELECT count(*) INTO caption FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 71 AND btrim(t.text) = 'CORRIGENDUM';
    SELECT count(*) INTO number_line FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 71
       AND t.text LIKE 'No.S.REG:4(47)/2020/165(A):- In the Sindh Government Gazette%'
       AND t.text LIKE '%Sindh Workers Welfare Board Employees (Service) Rules, 2021%';
    IF masthead <> 1 OR caption <> 1 OR number_line <> 1 THEN
        RAISE EXCEPTION 'page 71 of % does not print the issue date, the corrigendum caption and number (masthead %, '
            'caption %, number %)', a.doc, masthead, caption, number_line;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = a.doc AND i.source_observation_id = 4747
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document % has no active single-tree instrument (run the first segmentation)', a.doc;
    END IF;
END $$;

WITH args AS (SELECT * FROM k6_args),
active_instrument AS (
  SELECT i.id FROM instrument i, args
   WHERE i.document_id = args.doc AND i.source_observation_id = 4747
     AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT a.id, 4747, args.doc, args.blk, 71,
       'Law, Parliamentary Affairs & Criminal Prosecution Service Department Corrigendum No.S.REG:4(47)/2020/165(A) '
       'dated 1 July 2021 (to the Sindh Workers Welfare Board Employees (Service) Rules, 2021)',
       'notification', 2021, 'No.S.REG:4(47)/2020/165(A)', 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'plan', 'tools/evidence/multi-instrument-plans/doc-' || args.doc || '.json',
         'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-19-' || args.doc || '.json',
         'owner_question', jsonb_build_object('document_id', args.doc, 'question_id', 'q1', 'choice', 'split',
                                              'original_document_id', 4602,
                                              'original_export', '.artifacts/decision-review/exports/decision-review-2026-10-19-4602.json'),
         'source_facts', jsonb_build_array(
           'page 70 ends Appendix-6 (the gratuity nomination form: witnesses, the head of office''s lines) and the cut-off imprint ''... Government Press''',
           'page 71 opens a new Gazette issue: EXTRAORDINARY / Registered No. M324 / The Sindh Government Gazette / Published by Authority / KARACHI TUESDAY JULY 13, 2021 / PART-I',
           'then GOVERNMENT OF SINDH / LAW, PARLIAMENTARY AFFAIRS & CRIMINAL PROSECUTION SERVICE DEPARTMENT, ''Karachi, dated the 1st July,2021.'', the caption CORRIGENDUM and ''No.S.REG:4(47)/2020/165(A):- In the Sindh Government Gazette Extraordinary issue, Registered No.M324, Part-I, published on 18th June, 2021, in the titled Rules "The Sindh Workers Welfare Board Employees (Service) Rules, 2021, in Appendix-2, in (Part-III) "APPOINTMENT BY PROMOTION". in the Table, in column (1), the Deputy Director (Works) (BPS-18) and entries there-against in column (2) and (3), be read as follows:-''',
           'the TABLE (Name of Post | Persons Eligible | Conditions of Eligibility): Deputy Director (Works/Estate) (BPS-18). | Assistant Director/ Assistant Secretary (Works/Welfare/ Finance & Admn (BPS-17) | Atleast five years service in BPS-17 in relevant cadre, on seniority-cum-fitness.; signed ALI AHMED BALOCH, SECRETARY TO GOVERNMENT OF SINDH'),
         'reviewed_pages', jsonb_build_array(70, 71),
         'render_artifact', '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4602/images/page-071.png',
         'render_sha256', '20a5da9a2dda4fdd4e4dac4bb15353aaec68e6e86e9fd66aa7965b78e827e188')
  FROM active_instrument a CROSS JOIN args
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (PDF p71, the masthead of the Gazette of 13 July 2021, above the printed caption '
       'CORRIGENDUM) begins the Law Department''s corrigendum No.S.REG:4(47)/2020/165(A) of 1 July 2021 to the Sindh '
       'Workers Welfare Board Employees (Service) Rules, 2021 -- a separate instrument bound after the Rules (owner '
       'decision 2026-10-19, 4602 q1 split; precedents 1626, 1839, 4598).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-' || c.document_id || '.json',
                          'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-19-' || c.document_id || '.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c, k6_args args
 WHERE c.document_id = args.doc AND c.source_observation_id = 4747
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
 WHERE c.source_observation_id = 4747 AND c.method = 'claude.multi-expression-plan/1';
