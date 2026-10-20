-- DRAFT by agent K6 (19 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4479.sh with psql variables, because the document is the
-- OCR-promoted revision of 4479 whose id and block ids exist only after the promotion:
--   ./nz psql -v ON_ERROR_STOP=1 -v doc=<promoted id> -v blk=<E1's first span block> < this file
-- Source-verified boundary evidence for the reviewed split of that revision
-- (tools/evidence/multi-instrument-plans/doc-<promoted id>.json, written from claude/agK6/work/agK6-mkplan_4479.py).
--
-- The PDF (observation 4664, 'THE SINDH EDUCATION FOUNDATION (EMPLOYEES SERVICE) RULES, 2021', 21 pages) is the Sindh
-- Government Gazette of Thursday 31 March 2022: PDF p1 the masthead, CONTENTS and an SGA&CD leave notification; pp2-19
-- (gazette 193-210) the SE&LD notification No.SO(G-III)SE&LD/Rules/SEF/3-1290/2021 making the Employees Service Rules,
-- the preliminary rules 1)-2), Parts I-X (rules (1)-(77)), the signature, Schedule I and Schedule II (Schedule of
-- Posts, to p19's last table); then on p19 (gazette 210), below that table, the department's heading 'SCHOOL EDUCATION
-- AND LITERACY DEPARTMENT / Karachi, dated 28th March, 2022', the notification 'No. SO (G-III)SE&LD/Rules/SEF/3-1290/
-- 2021: Consequent upon the approval of Agenda Item No.6 ... the Government of Sindh is pleased to make the "Sindh
-- Education Foundation (Employees Gratuity Rules) 2021".', rules 1-13 to p21 and their signature. Read on the render
-- (agent K6, 19 Oct 2026): .artifacts/ocr-review-pack-owner-2026-10-17/doc-4479/images/page-019.png (888f4447...).
-- Owner: card claude/agK6/card-4479.json q2 'split' (the lead transcribes the answer for the promoted id in
-- decision-review-<date>-<promoted id>.json). The Service Rules open the document at its first block, so they need no
-- boundary row; the Gratuity Rules' span starts at their printed department heading on p19 and is anchored here.
--
-- Guards: the anchor must be the block on PDF page 19 of the promoted revision of 4479 that prints 'SCHOOL EDUCATION AND
-- LITERACY DEPARTMENT' and 'dated 28th March, 2022'; page 19 must print the Gratuity Rules' notification naming them and
-- rule 1's title (the span start checked against the printed heading and title); an active single-tree instrument must
-- exist (the first segmentation). Idempotent.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE k6_args ON COMMIT DROP AS SELECT :doc::bigint AS doc, :blk::bigint AS blk;

DO $$
DECLARE a k6_args%ROWTYPE; heading int; notif int; title int;
BEGIN
    SELECT * INTO a FROM k6_args;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = a.doc AND supersedes_document_id = 4479 AND is_active) THEN
        RAISE EXCEPTION 'document % is not the active promoted revision of 4479', a.doc;
    END IF;
    SELECT count(*) INTO heading FROM text_block t
     WHERE t.document_id = a.doc AND t.id = a.blk AND t.page_no = 19
       AND strpos(t.text, 'SCHOOL EDUCATION AND LITERACY DEPARTMENT') = 1 AND strpos(t.text, 'dated 28th March, 2022') > 0;
    SELECT count(*) INTO notif FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 19
       AND strpos(t.text, 'No. SO (G-III)SE&LD/Rules/SEF/3-1290/2021: Consequent upon the approval') = 1
       AND strpos(t.text, 'Sindh Education Foundation (Employees Gratuity Rules) 2021') > 0;
    SELECT count(*) INTO title FROM text_block t
     WHERE t.document_id = a.doc AND t.page_no = 19
       AND strpos(t.text, 'These Rules may be called the "Sindh Education Foundation (Employees Gratuity Rules) 2021"') = 1;
    IF heading <> 1 OR notif <> 1 OR title <> 1 THEN
        RAISE EXCEPTION 'block % of % is not the Gratuity Rules'' printed heading on page 19 over their notification and '
            'title (heading %, notification %, title %)', a.blk, a.doc, heading, notif, title;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i WHERE i.document_id = a.doc AND i.source_observation_id = 4664
                     AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document % has no active single-tree instrument (run the first segmentation)', a.doc;
    END IF;
END $$;

WITH args AS (SELECT * FROM k6_args),
active_instrument AS (
  SELECT i.id FROM instrument i, args
   WHERE i.document_id = args.doc AND i.source_observation_id = 4664
     AND i.is_active AND i.duplicate_of IS NULL
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id, source_observation_id, document_id, start_block_id, source_page,
    detected_title, detected_kind, detected_year, detected_number, confidence,
    method, evidence
)
SELECT a.id, 4664, args.doc, args.blk, 19,
       'The Sindh Education Foundation (Employees Gratuity Rules) 2021', 'rules', 2021, NULL, 1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'plan', 'tools/evidence/multi-instrument-plans/doc-' || args.doc || '.json',
         'owner_question', jsonb_build_object('card', 'claude/agK6/card-4479.json', 'document_id', args.doc,
                                              'question_id', 'q2', 'choice', 'split', 'original_document_id', 4479),
         'source_facts', jsonb_build_array(
           'page 19 (gazette 210) prints the last table of Schedule II (Schedule of Posts: Naib Qasid, Sanitary Worker ...), then',
           'SCHOOL EDUCATION AND LITERACY DEPARTMENT / Karachi, dated 28th March, 2022',
           'No. SO (G-III)SE&LD/Rules/SEF/3-1290/2021: Consequent upon the approval of Agenda Item No.6 by the Provincial Cabinet, Sindh, in its meeting held on December 02, 2021; the Government of Sindh is pleased to make the "Sindh Education Foundation (Employees Gratuity Rules) 2021".',
           '1. Title: These Rules may be called the "Sindh Education Foundation (Employees Gratuity Rules) 2021". ... 13. ... shall come into force with immediate effect (p21), signed (GHULAM AKBAR LAGHARI) SECRETARY TO GOVERNMENT OF SINDH'),
         'reviewed_pages', jsonb_build_array(19, 21),
         'render_artifact', '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4479/images/page-019.png',
         'render_sha256', '888f44473c8f24c5663f585a15bdd3f3da84e2f569ffb2a0e4faa61489828150')
  FROM active_instrument a CROSS JOIN args
ON CONFLICT (instrument_id, start_block_id, method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id, resolution, review_basis, method, rationale, evidence, decided_by
)
SELECT c.id, 'confirmed_split', 'source_verified', 'claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (PDF p19, the printed heading SCHOOL EDUCATION AND LITERACY DEPARTMENT, Karachi, '
       'dated 28th March, 2022) begins the notification making the Sindh Education Foundation (Employees Gratuity Rules) '
       '2021 -- a separate instrument printed after the Employees Service Rules'' Schedule II (owner card-4479 q2 split; '
       'precedents 4347, 3730, 3423, 4626).',
       jsonb_build_object('reviewer_type', 'assistant', 'source_start_block_id', c.start_block_id,
                          'plan', 'tools/evidence/multi-instrument-plans/doc-' || c.document_id || '.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c, k6_args args
 WHERE c.document_id = args.doc AND c.source_observation_id = 4664
   AND c.start_block_id = args.blk
   AND c.method = 'claude.multi-expression-plan/1'
   AND NOT EXISTS (SELECT 1 FROM segmentation_boundary_adjudication a
                    WHERE a.candidate_id = c.id AND a.resolution = 'confirmed_split');

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM segmentation_boundary_candidate c
                     JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id AND a.resolution = 'confirmed_split'
                     JOIN k6_args args ON c.document_id = args.doc AND c.start_block_id = args.blk) THEN
        RAISE EXCEPTION 'no confirmed_split at the Gratuity Rules'' span start';
    END IF;
END $$;

COMMIT;

SELECT c.id, c.start_block_id, c.source_page, left(c.detected_title, 80) AS title, a.resolution
  FROM segmentation_boundary_candidate c
  JOIN v_boundary_adjudication_latest a ON a.candidate_id = c.id
 WHERE c.source_observation_id = 4664 AND c.method = 'claude.multi-expression-plan/1';
