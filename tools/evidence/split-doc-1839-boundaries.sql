-- Source-verified boundary evidence for the reviewed split of Punjab document 1839
-- (tools/evidence/multi-instrument-plans/doc-1839.json).  Drafted by agent CL; renamed without the draft
-- suffix and applied by builder BZ on 9 Oct 2026.
--
-- The official PDF (observation 2060, catalogued as 'PUNJAB AGRICULTURE
-- DEPARTMENT, DIRECTORATE OF AGRICULTURE IN', 2007) prints five instruments:
-- pages 1-21 the S&GAD notification of 20 March 2007 making the Punjab
-- Agriculture Department, Directorate of Agriculture Information Service Rules,
-- 2007 (rules 1-3, distribution list, the Schedule rows 1-72), pages 22-25 the
-- amending notification of 22 August 2008, pages 26-28 that of 11 May 2011,
-- pages 29-31 that of 12 February 2012 and page 32 the corrigendum of 19 March
-- 2012 (to the 2012 notification).  The owner decided on 2026-10-08
-- (decision-review-2026-10-08-h.json, doc 1839 q1 'split', q2 'rows-by-serial').
-- The Rules open the document at block 124788, so they need no boundary row.
--
-- Doc 691 precedent: tools/evidence/split-doc-691-boundaries.sql.  This file
-- appends evidence only; materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 1839`, run while the
-- single-tree instrument is still active.  It needs agCL rules
-- apparatus_over_left_margin_heading (and the v4 rules in claude/agCL/pin-1839.json)
-- and SCHEDULE_GROUP_CAPTION_CHOICES admitting q2 'rows-by-serial' before it is run.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1839 AND i.source_observation_id=2060
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (125346::bigint,22,
     'S&GAD Notification No. SOR-III(S&GAD)1-10/99 dated 22 August 2008 (amending the Punjab Agriculture Department, Directorate of Agriculture Information Service Rules, 2007)',
     'notification',2008,'SOR-III(S&GAD)1-10/99',
     jsonb_build_array(
       'page 21 ends the 2007 Schedule with row 72 Sweeper and the rest of the page blank',
       'page 22 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES & GENERAL ADMINISTRATION / DEPARTMENT., ''Dated Lahore, the 22nd August, 2008'', NOTIFICATION, No.SOR-III(S&GAD)1-10/99 and the formula ''... the following amendments shall be made:''',
       'its AMENDMENTS (i) substitute the entries at serial Nos. 22, 25, 28, 36, 37, 59 and (ii) insert 59(a) (p24), signed JAVAID ASLAM, ADDITIONAL CHIEF SECRETARY; forwarded 30 August 2008 (p25)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1839-p22.png',
     '57be018390b8d9b8107d3151c5b5ee9f3909c49130718b545f4e32a2753eacea'),
    (125418::bigint,26,
     'S&GAD (Regulations Wing) Notification No. SOR(III)(S&GAD) 1-23/2010 dated 11 May 2011 (amending the Punjab Agriculture Department, Directorate of Agriculture Information Service Rules, 2007)',
     'notification',2011,'SOR(III)(S&GAD) 1-23/2010',
     jsonb_build_array(
       'page 25 ends the 2008 notification''s forwarding with ''SECTION OFFICER (B&A)''',
       'page 26 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES & GENERAL ADMINISTRATION / DEPARTMENT / (REGULATIONS WING), ''Dated Lahore, the 11th May, 2011'', NOTIFICATION, No.SOR(III)(S&GAD) 1-23/2010',
       'its AMENDMENTS insert rows 73-78 after Sr.No.72 (pp26-27), signed MUHAMMAD ILYAS; forwarded 20 May 2011 (pp27-28)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1839-p26.png',
     'e32d2499985d6af60fee56e58bbb02ba4dd7e7eea2a6adfd874e6fd64063727e'),
    (125482::bigint,29,
     'S&GAD (Regulations Wing) Notification No. SOR(III)(S&GAD) 1-23/2010 dated 12 February 2012 (amending the Punjab Agriculture Department, Directorate of Agriculture Information Service Rules, 2007)',
     'notification',2012,'SOR(III)(S&GAD) 1-23/2010',
     jsonb_build_array(
       'page 28 ends the 2011 notification''s forwarding with GOVERNMENT OF THE PUNJAB / AGRICULTURE DEPARTMENT and the rest of the page blank',
       'page 29 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES & GENERAL ADMINISTRATION / DEPARTMENT / (REGULATIONS WING), ''Dated Lahore, the 12th February, 2012'', NOTIFICATION',
       'its AMENDMENTS (a) substitute column 7 at serial No.22 and (b) insert rows 60)-62) after Sr.No.59(a) (pp29-30); forwarded ''29th February, 2010'' (sic, p30) and by the Agriculture Department on 06-03-2012 (p31)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1839-p29.png',
     '6c8f3c1cac85406c222f55803ae7b9bcd270d406e96077a6477376d6dbac31a9'),
    (125538::bigint,32,
     'S&GAD (Regulations Wing) Corrigendum No. SOR-III(S&GAD)1-23/2010 dated 19 March 2012 (to Notification No. SOR-III(S&GAD)1-23/2010 dated 12 February 2012)',
     'notification',2012,'SOR-III(S&GAD)1-23/2010',
     jsonb_build_array(
       'page 31 ends the 2012 notification''s endorsement with ''SECTION OFFICER (A-I)''',
       'page 32 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES & GENERAL ADMINISTRATION / DEPARTMENT / (REGULATIONS WING), ''Dated Lahore, the 19th March, 2012'', CORRIGENDUM',
       'the corrigendum reads Sr.No.62 ''Video Operator (BS-15'' of the 12-02-2012 notification as ''Video Editor (BS-15)'', signed MUHAMMAD ILYAS'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1839-p32.png',
     '034afa61c14cd85da9e0dcc7a46d63d678a62603c4ffaed796ec2eb52e7cb64d')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2060,1839,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1839.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
         'source_facts',p.source_facts,
         'reviewed_pages',(SELECT jsonb_agg(g) FROM generate_series(1,32) g),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 125346 THEN 'Block 125346 begins the S&GAD notification of 22 August 2008 amending the Schedule of the Punjab Agriculture Department, Directorate of Agriculture Information Service Rules, 2007 -- a separate amending instrument (owner decision 2026-10-08, export -h q1 split).'
         WHEN 125418 THEN 'Block 125418 begins the S&GAD notification of 11 May 2011 inserting rows 73-78 in the Schedule of the 2007 Rules -- a separate amending instrument (owner decision 2026-10-08, export -h q1 split).'
         WHEN 125482 THEN 'Block 125482 begins the S&GAD notification of 12 February 2012 amending the Schedule of the 2007 Rules -- a separate amending instrument (owner decision 2026-10-08, export -h q1 split).'
         ELSE 'Block 125538 begins the S&GAD corrigendum of 19 March 2012 to the notification of 12 February 2012 -- a separate instrument (owner decision 2026-10-08, export -h q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1839.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1839 AND c.source_observation_id=2060
   AND c.start_block_id IN (125346,125418,125482,125538)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
