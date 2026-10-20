-- Drafted by agent JE (12 Oct 2026, prepare mode); renamed and applied by builder BZ on 13 Oct 2026. Source-verified
-- boundary evidence for the reviewed split of document 4378 (tools/evidence/multi-instrument-plans/doc-4378.json).
--
-- Observation 1898 (kpcode.kp.gov.pk THE_KHYBER_PAKHTUNKHWA_FINANCE_ACT_2022.pdf, SHA-256 3d8d4dad...), 32 pages.
-- Owner decision: decision-review-2026-10-12-j.json, document 4378, q1 'split' -- the Khyber Pakhtunkhwa Public
-- Financial Management Act, 2022 becomes a separate, embedded instrument with its own ss.1-48 and chapters; the
-- Finance Act keeps ss.1-10, and s.10 holds the enacting words.
--
-- Read from the renders (agent JE): p1 (0de778dc...) the copy's contents -- Finance Act rows 1-10 (blocks
-- 710632-710642), then 'AN ACT', 'CHAPTER-I PRELIMINARY', rows 1-48 of the PFM Act (710643-710699, to p3), then the
-- Finance Act's 'Appendix-I [see section 3]' / 'Appendix-II [see section 4]' rows (710700-710704); p4 (63332263...)
-- the Finance Act's title, preamble, s.1; p10 (30a8413a...) s.10's enacting words, then the quoted '“An Act to
-- provide for efficient and transparent management ...' (block 710757), its preamble, Chapter I, s.1; p11 (6c67d569...)
-- PFM s.2 Definitions; p29 the PFM Act ends with s.48 '... before the commencement of this Act.”.' (block 710859);
-- p30 (0ecb0360...) the Finance Act's Appendix-I resumes (block 710861).
--
-- Expression 1 (embedded) spans 710643-710699 (its contents rows) and 710757-710859 (its text); its first span start
-- 710643 is the anchor the materializer requires; 710757 is the start of its quoted text. Materialisation is the
-- separate, dry-run-gated `tools/materialize_multi_instrument.py --document 4378` after the plan is renamed, the
-- readings claude/agJE/patch-4378.json are recorded and observation 1898 is pinned unreleased-v4 (in-memory build:
-- e0 48 nodes, S7 [], contents 10/10 linked; e1 238 nodes, S7 []).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=4378 AND i.source_observation_id=1898
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (710643::bigint,1,'The Khyber Pakhtunkhwa Public Financial Management Act, 2022','act',2022,NULL::text,
     jsonb_build_array(
       'page 1 lists, after the Finance Act''s rows 1-10, a second contents headed AN ACT with Chapters I-VIII and sections 1-48 (to page 3)',
       'those rows are the contents of the Act that the Finance Act''s s.10 enacts',
       'the Finance Act''s own appendix rows follow them on page 3'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4378-p1.png',
     '0de778dcbb8fe6db4314e47b8b4abb7a46b149face89f1df16685f0e46d63866'),
    (710757::bigint,10,'The Khyber Pakhtunkhwa Public Financial Management Act, 2022','act',2022,NULL::text,
     jsonb_build_array(
       'page 10 prints s.10 of the Finance Act, Enactment of the Khyber Pakhtunkhwa Public Financial Management Act, 2022, ending in the manner as follows:',
       'then the quoted Act: “An Act to provide for efficient and transparent management of the Provincial Consolidated Fund ..., its preamble and enacting formula, CHAPTER-I PRELIMINARY and s.1 naming it the Khyber Pakhtunkhwa Public Financial Management Act, 2022',
       'the quoted Act runs to s.48 on page 29 and closes there; the Finance Act''s Appendix-I resumes on page 30'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4378-p10.png',
     '30a8413ae12df5079a0444cd0cceaca0d8529c17eae07d1b14a1578c5127db54')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,1898,4378,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4378.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'question_id','q1',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,10,11,29,30),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 710643 THEN 'Block 710643 begins the contents of the Khyber Pakhtunkhwa Public Financial Management Act, 2022, the Act enacted by s.10 of the Finance Act (owner decision 2026-10-12 export j q1 split).'
         ELSE 'Block 710757 begins the text of the Khyber Pakhtunkhwa Public Financial Management Act, 2022, quoted in s.10 of the Finance Act (owner decision 2026-10-12 export j q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4378.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=4378 AND c.source_observation_id=1898
   AND c.start_block_id IN (710643,710757)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
