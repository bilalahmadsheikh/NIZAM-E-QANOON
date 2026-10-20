-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4640.sh:
--   ./nz psql -v ON_ERROR_STOP=1 < this file
-- Source-verified boundary evidence for the reviewed split of document 4640, the promoted OCR revision of 4442
-- (tools/evidence/multi-instrument-plans/doc-4640.json, written from claude/agK6/work/agK6-mkplan_4640.py).
--
-- The Sindh Govt. Gazette Ext. of 25 January 2017, Part-I (observation 4555, 40 pages) prints two sets of rules of the
-- Rehabilitation Department / PDMA Sindh: pp1-8 the 'Provincial Disaster Management Authority Sindh Service Rules
-- 2016' (rules 1-23, ending on p8 with '23. GENERAL:' and the signature 'SECRETARY TO GOVERNMENT OF SINDH', block
-- 970060), and pp9-40 the 'Provincial Disaster Management Authority Sindh (Conduct of Business) Rules,2016', opening on
-- p9 (gazette p82) under its own notification 'NO:PDMA(S)/11(2)/2014:- In, exercise of the powers conferred under
-- section 47 of the National Disaster Management Act-2010, the Government of Sindh are pleased to make the following
-- rules, namely:-' (block 970064) with rule 1(1) 'These rules may be called the Provincial Disaster Management Authority
-- Sindh (Conduct of Business) Rules,2016.' (block 970066). Owner: export m (decision-review-2026-10-16-m.json), 4640 q1
-- 'split'. The Service Rules open the document at its first block and need no boundary row; the Conduct of Business
-- Rules' span starts at the notification (block 970064) and is anchored here.
--
-- Guards: 4640 must be the active promoted revision of 4442 with an active single-tree instrument of observation 4555;
-- the anchor must be the page-9 block opening 'NO:PDMA(S)/11(2)/2014:- In, exercise of the powers conferred under
-- section 47'; the next block in reading order must be rule 1's heading and the one after it must print the title
-- '(Conduct of Business) Rules,2016'; the last block of p8 must be the Service Rules' signature. Idempotent.

\set ON_ERROR_STOP on
BEGIN;

DO $$
DECLARE anchor_ok int; next_ok int; title_ok int; sig_ok int;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = 4640 AND supersedes_document_id = 4442 AND is_active) THEN
        RAISE EXCEPTION 'document 4640 is not the active promoted revision of 4442';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = 4640 AND i.source_observation_id = 4555
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document 4640 has no active single-tree instrument of observation 4555';
    END IF;
    SELECT count(*) INTO anchor_ok FROM text_block t
     WHERE t.id = 970064 AND t.document_id = 4640 AND t.page_no = 9
       AND t.text LIKE 'NO:PDMA(S)/11(2)/2014:- In, exercise of the powers conferred under section 47%';
    SELECT count(*) INTO next_ok FROM text_block t
     WHERE t.id = 970065 AND t.document_id = 4640 AND t.page_no = 9
       AND t.text LIKE '1. SHORT TITLE, APPLICABILITY AND COMMENCEMENT%';
    SELECT count(*) INTO title_ok FROM text_block t
     WHERE t.id = 970066 AND t.document_id = 4640 AND t.page_no = 9
       AND t.text LIKE '%Provincial Disaster Management Authority Sindh (Conduct of Business) Rules,2016%';
    SELECT count(*) INTO sig_ok FROM text_block t
     WHERE t.id = 970060 AND t.document_id = 4640 AND t.page_no = 8
       AND btrim(t.text) = 'SECRETARY TO GOVERNMENT OF SINDH'
       AND NOT EXISTS (SELECT 1 FROM text_block u WHERE u.document_id = 4640 AND u.page_no = 8
                         AND u.reading_order > t.reading_order);
    IF anchor_ok <> 1 OR next_ok <> 1 OR title_ok <> 1 OR sig_ok <> 1 THEN
        RAISE EXCEPTION 'the printed boundary does not check (anchor %, rule 1 heading %, title %, p8 signature %)',
            anchor_ok, next_ok, title_ok, sig_ok;
    END IF;
END $$;

WITH active_instrument AS (
  SELECT i.id FROM instrument i
   WHERE i.document_id = 4640 AND i.source_observation_id = 4555 AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT a.id, 4555, 4640, 970064, 9,
       'Provincial Disaster Management Authority Sindh (Conduct of Business) Rules, 2016',
       'rules', 2016, 'NO:PDMA(S)/11(2)/2014', 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'plan', 'tools/evidence/multi-instrument-plans/doc-4640.json',
         'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json',
         'owner_question', jsonb_build_object('document_id', 4640, 'question_id', 'q1', 'choice', 'split'),
         'source_facts', jsonb_build_array(
           'p8 (gazette p81) ends the Service Rules with ''23. GENERAL: In all matters not expressly provided in these rules, members of the service shall be governed by such rules and orders of Government.'' and the signature ''SECRETARY TO GOVERNMENT OF SINDH''',
           'p9 (gazette p82) opens with the notification ''NO:PDMA(S)/11(2)/2014:- In, exercise of the powers conferred under section 47 of the National Disaster Management Act-2010, the Government of Sindh are pleased to make the following rules, namely:-''',
           'then ''1. SHORT TITLE, APPLICABILITY AND COMMENCEMENT:- (1) These rules may be called the Provincial Disaster Management Authority Sindh (Conduct of Business) Rules,2016. (2) These rules shall come into force at once.'' and ''2. DEFINITIONS:''',
           'the Conduct of Business Rules run to rule 48 (Chapters I-VIII; no Chapter VII and no rule 41 printed) and end on p40 with ''SECRETARY TO GOVT. OF SINDH'''),
         'reviewed_pages', jsonb_build_array(8, 9),
         'render_artifact', '.artifacts/ocr-review-pack-r5/doc-4442/images/page-009.png',
         'render_sha256', 'ad32b85feaf467876fab70e4b9c0ec133d24caef8db1d1610c1b2a63ccce47a9')
  FROM active_instrument a
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block 970064 (PDF p9, gazette p82, the notification ''NO:PDMA(S)/11(2)/2014:- In, exercise of the powers '
       'conferred under section 47 ...'') begins the Provincial Disaster Management Authority Sindh (Conduct of '
       'Business) Rules,2016 (its title printed in rule 1(1), block 970066) -- a separate set of rules bound after the '
       'Service Rules, which end on p8 with their signature (owner export m, 4640 q1 split).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-4640.json',
                          'owner_decision', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id = 4640 AND c.source_observation_id = 4555 AND c.start_block_id = 970064
   AND c.method = 'claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id = c.id AND a.resolution = 'confirmed_split');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate c
                     JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
                    WHERE c.document_id = 4640 AND c.start_block_id = 970064) THEN
        RAISE EXCEPTION 'no confirmed_split at the Conduct of Business Rules'' span start';
    END IF;
END $$;

COMMIT;

SELECT c.id, c.start_block_id, c.source_page, left(c.detected_title, 80) AS title, a.resolution
  FROM segmentation_boundary_candidate c
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id = 4555 AND c.method = 'claude.multi-expression-plan/1';
