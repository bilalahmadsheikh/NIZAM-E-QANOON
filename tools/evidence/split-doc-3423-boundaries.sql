-- Drafted by agent K3 (15 Oct 2026); adopted by builder BZ 16 Oct 2026 (renamed from -DRAFT; applied by the owner-run batch). Source-verified boundary evidence for splitting document
-- 3423 (catalogue 'Subject: THE PUNJAB EMPLOYEES EFFICIENCY, DISCIPLINE AND ACCOUNTABILITY (AMENDMENT) ACT, 2014 ...',
-- observation 2733) by the reviewed plan tools/evidence/multi-instrument-plans/doc-3423.json (to be adopted as
-- doc-3423.json; 3423 is today in tools/materialize_multi_instrument.py COMPILATION_DOCUMENTS -- the lead takes it off
-- that list when the plan is adopted, as for 3389).
--
-- Owner decisions: decision-review-2026-10-12-j.json 3423 q1 'main-plus-notifications'; decision-review-2026-10-15-
-- delegated.json 3423 q2 'split-annexes-v-vi' (card claude/agK3/card-3423-q2.json).
-- E0 opens the document (first block 374457, p1 letterhead of the 17 Aug 2015 notification): no anchor needed (3389
-- precedent). E0's second span (374740, p20, Annex VII) is a span start, not an expression start: no candidate.
-- Each embedded expression starts on its printed letterhead (renders read by agent K3):
--   E1 374706 (p18, render 2da44c45...): 'GOVERNMENT OF THE PUNJAB SERVICES & GEN. ADMN. DEPARTMENT (REGUALTIONS WING)
--      Dated Lahore, the 13th February, 2013 NOTIFICATION NO.SORI(S&GAD)1-30/2003.- In exercise of the powers conferred
--      on him under sub-clause (ii) of clause (f) of Section 2 ...', the Table, the Explanation, signed SHAHNAZ NAWAZ;
--   E2 374723 (p19, render d2d95d25...): the same letterhead dated 6th February, 2007, NOTIFICATION
--      NO.SORI(S&GAD)1-30/2003.-, the Table (Surplus Pool, retired employees), the Explanation, 'BY ORDER OF THE CHIEF
--      MINISTER PUNJAB ADDITIONAL CHIEF SECRETARY'.
-- The candidates are keyed to the active UNRELEASED instrument 4f01e17a-5e33-4e3b-b6c6-62169fe8b84f (expression 0;
-- Checked 16 Oct (read only): segmentation_boundary_candidate carries no trigger and no span constraint (UNIQUE
-- (instrument_id,start_block_id,method), FKs to instrument/document/observation/text_block, confidence and page checks
-- only), so a candidate need not lie inside the keyed instrument's stored assignment; earlier inactive instruments of
-- observation 2733 span 374457-374874, which contains both starts). Observation 2733 has no live or archived boundary
-- candidate (checked 15 Oct). Nothing is released.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id, i.source_observation_id
    FROM instrument i
   WHERE i.document_id=3423 AND i.expression_ordinal=0
     AND i.id='4f01e17a-5e33-4e3b-b6c6-62169fe8b84f'
     AND i.is_active AND i.duplicate_of IS NULL
     AND i.source_observation_id=2733
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (374706::bigint,18,'Notification No. SORI(S&GAD)1-30/2003, 13 February 2013','notification',2013,'SORI(S&GAD)1-30/2003',
     jsonb_build_array(
       'page 18 prints the S&GAD letterhead dated 13th February, 2013 and NOTIFICATION NO.SORI(S&GAD)1-30/2003 under s.2(f)(ii) of the PEEDA Act 2006, with its Table and Explanation, signed Secretary (Regulations) S&GAD',
       'the Guidebook (p3) names it: vide notification No.SORI(S&GAD)1-30/03 dated 13-02-2013 (Annex-V)',
       'page 17 before it ends Annex IV, the model draft personal hearing notice'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3423-p18.png',
     '2da44c455df168487f9931ea6b94ca7d53e58bf176ff7380ebba0b0f5130326d'),
    (374723::bigint,19,'Notification No. SORI(S&GAD)1-30/2003, 6 February 2007','notification',2007,'SORI(S&GAD)1-30/2003',
     jsonb_build_array(
       'page 19 prints the S&GAD letterhead dated 6th February, 2007 and NOTIFICATION NO.SORI(S&GAD)1-30/2003 under s.2(f)(ii) of the PEEDA Act 2006, with its Table and Explanation, BY ORDER OF THE CHIEF MINISTER PUNJAB',
       'the Guidebook (p3) names it: vide notification No.SORI(S&GAD)1-30/2003 dated 06-02-2007 (Annex-VI)',
       'page 18 before it is the 13 February 2013 notification'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3423-p19.png',
     'd2d95d25532c490bc5557eb84c441b3486b9d50bf7183bfba878223899775a0e')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,a.source_observation_id,3423,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3423.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json',
         'question_id','q2',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,3,13,14,17,18,19,20),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 374706 THEN 'Block 374706 begins Notification No. SORI(S&GAD)1-30/2003 of 13 February 2013 (Annex V of the Guidebook), its own instrument (owner decisions 2026-10-12 export j q1, 2026-10-15 delegated q2 split-annexes-v-vi).'
         ELSE 'Block 374723 begins Notification No. SORI(S&GAD)1-30/2003 of 6 February 2007 (Annex VI of the Guidebook), its own instrument (owner decisions 2026-10-12 export j q1, 2026-10-15 delegated q2 split-annexes-v-vi).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3423.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3423
   AND c.start_block_id IN (374706,374723)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
