-- Drafted (renamed and applied by builder BZ, 14 Oct 2026); DRAFT by agent JB (13 Oct 2026, prepare mode; not applied). Source-verified boundary evidence for splitting document
-- 3392 ('ELECTRICITY DUTY RULE 1964', observation 2224) by the reviewed plan
-- tools/evidence/multi-instrument-plans/doc-3392.json (to be adopted as doc-3392.json; 3392 is in neither
-- PRIMARY_DOCUMENTS nor COMPILATION_DOCUMENTS, so the plan file alone routes it).
--
-- Owner decision: decision-review-2026-10-12-j.json, document 3392, q1 'split'. No expression opens the document (its
-- first block 367774 is the compiler's p1 contents, outside every span), so every expression's first span start needs a
-- confirmed_split anchor (doc 977 precedent). Observation 2224 has no live and no archived boundary candidate.
-- Each span start is the expression's printed title (page renders, agent JB 13 Oct):
--   E0 367876 (p6, render 95d19843...): 'THE WEST PAKISTAN ELECTRICITY DUTY RULES, 1964' (note 4), then
--      'Notification No. S.O.PP-3/5-64,-- In exercise of the powers conferred ... the Government of West Pakistan is
--      pleased to make the following Rules', rule 1 'These Rules may be called the West Pakistan Electricity Duty
--      Rules, 1964.' -- the title, the notification and rules 1-4 are one extracted block;
--   E1 367790 (p2, render d7e720cf...): 'THE WEST PAKISTAN FINANCE ACT, 1964' above '[ACT XXXIV OF 1964]', the
--      compiler's date, and the reproduced s.13 with the Fifth and Sixth Schedules (pp2-3); the compiler's caption
--      'IMPOSITION OF ELECTRICITY DUTY' (367789) above it stays outside;
--   E2 367858 (p5, render 6572a0f7...): 'WEST PAKISTAN FINANCE ACT (BALOCHISTAN AMENDMENT ACT)', 'ACT [VII OF 1974]
--      (Balochistan Gazette, Extra.)', '[10th July, 1974]', 'AN ACT To amend the West Pakistan Finance Act, 1964, in its
--      application to the Province of Balochistan', ss.1-2 and its Fifth and Sixth Schedules (pp5-6).
-- The candidates are keyed to the active UNRELEASED instrument b2244f98-6cb9-4ff8-ba88-cb369db6bb60 (expression 0,
-- span 367774-367924), whose tree spans all three starts. Nothing in this document is released.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id, i.source_observation_id
    FROM instrument i
   WHERE i.document_id=3392 AND i.expression_ordinal=0
     AND i.id='b2244f98-6cb9-4ff8-ba88-cb369db6bb60'
     AND i.is_active AND i.duplicate_of IS NULL
     AND i.source_observation_id=2224
     AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (367876::bigint,6,'West Pakistan Electricity Duty Rules, 1964','rules',1964,NULL::text,
     jsonb_build_array(
       'page 6 prints the title THE WEST PAKISTAN ELECTRICITY DUTY RULES, 1964 after the Balochistan Act''s Sixth Schedule item 7',
       'Notification No. S.O.PP-3/5-64 makes the Rules under s.17(1)(iii) and (vi) of the West Pakistan Finance Act, 1964; rule 1 names them',
       'rules 1-12 and Forms A and B follow to the end of the file (p9)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3392-p6.png',
     '95d198433bfee37df29f91699cf88d7f762ebe91c8556feea665f1429ccacc76'),
    (367790::bigint,2,'West Pakistan Finance Act, 1964','act',1964,'XXXIV',
     jsonb_build_array(
       'page 2 prints THE WEST PAKISTAN FINANCE ACT, 1964 [ACT XXXIV OF 1964] under the compiler''s caption IMPOSITION OF ELECTRICITY DUTY',
       'the compiler states that s.13 of the Act is reproduced below; s.13 (1)-(4) follows, then the Fifth and Sixth Schedules (p3)',
       'page 1 before it is the compiler''s contents of the whole file'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3392-p2.png',
     'd7e720cfae3d4e377de1b77544a7b2fd2c74d4d01377f03015ff1804076f5335'),
    (367858::bigint,5,'West Pakistan Finance Act (Balochistan Amendment) Act, 1974','act',1974,'VII',
     jsonb_build_array(
       'page 5 prints the title of a separate Act, ACT [VII OF 1974] (Balochistan Gazette, Extra.), dated [10th July, 1974], with AN ACT, its long title and preamble',
       'its s.1 names it the West Pakistan Finance Act (Balochistan Amendment) Act, 1974; s.2 substitutes the Fifth and Sixth Schedules set forth after it',
       'before it the page ends the compiler''s note on the Punjab Finance Ordinance, 1978'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3392-p5.png',
     '6572a0f75a6e737fa04bb6f3a1194234c7d40b9fa419ca76b679bc9f2855ce2f')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,a.source_observation_id,3392,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3392.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'question_id','q1',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8,9),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 367876 THEN 'Block 367876 begins the West Pakistan Electricity Duty Rules, 1964 (Notification No. S.O.PP-3/5-64), printed after the Balochistan Amendment Act (owner decision 2026-10-12 export j q1 split).'
         WHEN 367790 THEN 'Block 367790 begins the reproduced West Pakistan Finance Act, 1964 (s.13 and the Fifth and Sixth Schedules), printed after the compiler''s contents (owner decision 2026-10-12 export j q1 split).'
         ELSE 'Block 367858 begins the West Pakistan Finance Act (Balochistan Amendment) Act, 1974 (VII of 1974), printed after the compiler''s Punjab and Sindh material (owner decision 2026-10-12 export j q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3392.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3392
   AND c.start_block_id IN (367876,367790,367858)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
