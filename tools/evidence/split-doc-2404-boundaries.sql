-- Drafted (renamed and applied by builder BZ, 14 Oct 2026); DRAFT (agent JA, 13 Oct 2026, PREPARE MODE -- not run). Source-verified boundary evidence for the reviewed split
-- of Punjab document 2404 (plan: tools/evidence/multi-instrument-plans/doc-2404.json, to be renamed
-- doc-2404.json when the lead adopts it; this file then loses -DRAFT).  Pattern: split-doc-268-boundaries.sql.
--
-- The official PDF (observation 2503, https://punjabcode.punjab.gov.pk/uploads/articles/service-rules-pimpd-pdf.pdf,
-- SHA-256 8186ad0205f33818c93a69378e0c79eaab5f40d7fe5c4ce66cc8db1a7d6c4216, 8 pages) binds four S&GAD notifications:
-- p1 the Punjab Institute of Management and Professional Department (PIMPD)/Management and Professional Development
-- Department, Recruitment Rules, 2007 (1 Nov 2007; opens the document at block 196931, no boundary row); p2 the
-- Punjab Management and Professional Development Department (Miscellaneous Posts) Service Rules 2010 (12 Aug 2010,
-- block 196947); pp3-5 the notification of 16 Feb 2012 inserting entries in the 2010 Rules' Schedule (block 196961);
-- pp6-8 the notification of 17 Aug 2012 inserting entries in the 2007 Rules' Schedule (block 197032).  Owner
-- decision: .artifacts/decision-review/exports/decision-review-2026-10-12-j.json, document 2404, q1 'split' (four instruments; distribution lists and signatures apparatus).
--
-- ORDER: 1. record the readings claude/agJA/patch-2404.json (tools/record_curation_patch.py --apply);
--        2. this file, while the single-tree instrument a7f78fbe-... is still active (the candidates key to it);
--        3. tools/materialize_multi_instrument.py --document 2404 (dry run, then --apply);
--        4. tools/evidence/declare-source-incompleteness-2404-DRAFT.sql (the Schedules not printed, owner q2).
-- This file appends evidence only.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=2404 AND i.source_observation_id=2503
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (196947::bigint,2,
     'The Punjab Management and Professional Development Department (Miscellaneous Posts) Service Rules, 2010',
     'rules',2010,NULL::text,
     jsonb_build_array(
       'page 2 opens a separate S&GAD notification dated 12 August 2010, No.SOR-III(S&GAD) 1-15/2010',
       'its own enabling formula and rules 1-3, rule 1 citing the Punjab Management and Professional Development Department (Miscellaneous Posts) Service Rules 2010',
       'its own signature (Muhammad Ilyas), endorsement of 18 August 2010 and distribution list',
       'page 1 before it is the 2007 Recruitment Rules, a different instrument'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p2.png', 'da6256fe3fcfa9d8187518b9bc8ae3f9eef4cf15a95154508cf350d3bf4bd098'),
    (196961::bigint,3,
     'Notification No. SOR-III(S&GAD) 1-15/2010 dated 16-02-2012 (amending the Punjab Management and Professional Development Department (Miscellaneous Posts) Service Rules, 2010)',
     'notification',2012,'SOR-III(S&GAD) 1-15/2010',
     jsonb_build_array(
       'page 3 opens an S&GAD (Regulations Wing) notification dated 16 February 2012',
       'it directs amendments to the 2010 Service Rules: AMENDMENTS / in the Schedule, after the existing entries, entries in columns 1 to 10 inserted (Research Officer, Research Assistant)',
       'signed on p4 (Muhammad Ilyas) with its own distribution list; p5 the Section Officer''s signature'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p3.png', '26851785e8f9d6e92a5bea5ff51be0e05d75e9f8d440f9f7b21fae2ca68c4745'),
    (197032::bigint,6,
     'Notification No. SOR-III(S&GAD) 1-15/2010 dated 17-08-2012 (amending the Punjab Institute of Management and Professional Department (PIMPD)/Management and Professional Development Department, Recruitment Rules, 2007)',
     'notification',2012,'SOR-III(S&GAD) 1-15/2010',
     jsonb_build_array(
       'page 6 opens an S&GAD (Regulations Wing) notification dated 17 August 2012',
       'it directs amendments to the 2007 Recruitment Rules: AMENDMENTS / in the Schedule, after the existing entries, entries in columns 1 to 10 inserted (Director Academic/Additional Chief Instructor, Deputy Director (Administration), Accounts Officer)',
       'signed on p7 (Shahnaz Nawaz, endorsement 3 September 2012) with its own distribution list on p8'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p6.png', 'd44a66f63f90345bbe812b7a9c848fbd4385b19c101215366da4b2d118a88349')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2503,2404,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-2404.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 196947 THEN 'Block 196947 begins the 12 Aug 2010 S&GAD notification making the Punjab Management and Professional Development Department (Miscellaneous Posts) Service Rules 2010, an instrument separate from the 2007 Recruitment Rules on page 1 (owner decision export j q1 split).'
         WHEN 196961 THEN 'Block 196961 begins the 16 Feb 2012 S&GAD notification amending the Schedule of the 2010 Service Rules, a separate amending instrument (owner decision export j q1 split).'
         ELSE 'Block 197032 begins the 17 Aug 2012 S&GAD notification amending the Schedule of the 2007 Recruitment Rules, a separate amending instrument (owner decision export j q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-2404.json',
                          'owner_decision',jsonb_build_object('export','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json','document_id',2404,'question_id','q1')),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=2404 AND c.source_observation_id=2503
   AND c.start_block_id IN (196947,196961,197032)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
