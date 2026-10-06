-- Source-verified boundary evidence for the reviewed split of Punjab document 268
-- (tools/evidence/multi-instrument-plans/doc-268.json).  NOT YET APPLIED.
--
-- The official PDF (observation 2767) prints three instruments: page 1 the
-- 27-06-2003 notification amending the 1996 Rules (its substituted Schedule
-- follows on pages 6-7), page 2 the 1996 Rules themselves (their original
-- Schedule on pages 4-5), and page 3 the 30-12-1998 Order.  The owner decided
-- this grouping on 2026-10-06 (decision-review-2026-10-06-b.json, doc 268 q1
-- 'other', q2 'as-amended').  The 2003 notification opens the document at
-- block 11925, so it needs no boundary row; the 1996 Rules (block 11939, p2)
-- and the 1998 Order (block 11951, p3) do.  Doc 977 precedent:
-- tools/evidence/release-docs-500-793-977-1729-1879.sql.
--
-- This file appends evidence only.  Materialisation is the separate,
-- dry-run-gated `tools/materialize_multi_instrument.py --document 268`.
-- Run it while the single-tree instrument is still active (the candidate is
-- keyed to it); the materializer refuses --apply without these two rows.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=268 AND i.source_observation_id=2767
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (11939::bigint,2,
     'The Punjab Excise and Taxation Department (Internal Audit) Service Rules, 1996',
     'rules',1996,NULL::text,
     jsonb_build_array(
       'page 2 opens a separate notification of the Services & General Administration Department',
       'its own enabling formula and the printed title THE PUNJAB EXCISE AND TAXATION DEPARTMENT (INTERNAL AUDIT) SERVICE RULES, 1996 (blocks 11944-11945)',
       'rules 1-3, the third annexing the Schedule printed on pages 4-5',
       'page 1 before it is the 2003 notification amending these Rules'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc268-p2.png',
     '3f1759c13def4c54df0364158c34b3ed9b4d9c5de697a1eb1abfc19f7c1fe993'),
    (11951::bigint,3,
     'Excise & Taxation Department Order No. SOAI(E&T)3-10/93 dated 30-12-1998',
     'order',1998,'SOAI(E&T)3-10/93',
     jsonb_build_array(
       'page 3 opens an ORDER of the Excise & Taxation Department under its own number and date',
       'it upgrades and re-designates posts; it is not a rule of the 1996 Rules',
       'signed by the Secretary, Excise & Taxation, with its own endorsements'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc268-p3.png',
     'b00bdf43bb1ba736a934b628d09de4458870788415403c43e297efa905af7925')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2767,268,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-268.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-06-b.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 11939 THEN 'Block 11939 begins the 1996 notification making the Punjab Excise and Taxation Department (Internal Audit) Service Rules, 1996 -- the principal instrument, separate from the 2003 amending notification printed before it on page 1 (owner decision 2026-10-06).'
         ELSE 'Block 11951 begins the Excise & Taxation Department Order of 30-12-1998, a separate departmental instrument and not part of the Rules (owner decision 2026-10-06).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-268.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-06-b.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=268 AND c.source_observation_id=2767
   AND c.start_block_id IN (11939,11951)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
