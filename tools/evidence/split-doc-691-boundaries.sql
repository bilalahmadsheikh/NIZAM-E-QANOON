-- Source-verified boundary evidence for the reviewed split of Punjab document 691
-- (tools/evidence/multi-instrument-plans/doc-691.json).  NOT YET APPLIED.
--
-- The official PDF (observation 2036, catalogued as 'SERVICE RULES', 2011)
-- prints four instruments: pages 1-4 the S&GAD notification of 24 May 2011,
-- pages 5-6 the notification of 28 October 2009, pages 6-8 the notification
-- of 13 September 2007 -- each amending the Environment Protection Department
-- Service Rules, 1997 -- and pages 8-14 the notification of 28 November 1997
-- making those Rules (a recruitment table, rows 1-35).  The owner decided
-- this grouping on 2026-10-06 (decision-review-2026-10-06-c.json, doc 691 q3
-- 'split-four', q2 'rows-by-serial').  The 2011 notification opens the
-- document at block 29625, so it needs no boundary row; the 2009 notification
-- (block 29735, p5), the 2007 notification (block 29768, p6) and the 1997
-- Rules (block 29847, p8) do.  Doc 977 / doc 268 precedent:
-- tools/evidence/release-docs-500-793-977-1729-1879.sql,
-- tools/evidence/split-doc-268-boundaries.sql.
--
-- This file appends evidence only.  Materialisation is the separate,
-- dry-run-gated `tools/materialize_multi_instrument.py --document 691`.
-- Run it while the single-tree instrument is still active (the candidate is
-- keyed to it); the materializer refuses --apply without these three rows.
-- The readings (claude/agAY/patch-691.json) need two parser rules that do not
-- exist yet (unlabelled_schedule_opener, quoted_table_row_text; see
-- claude/agAY-log.md, doc 691): do not materialize before they do.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=691 AND i.source_observation_id=2036
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (29735::bigint,5,
     'S&GAD (Regulations Wing) Notification No. SO(R-III) (S&GAD)/1-24/2007 dated 28 October 2009 (amending the Environment Protection Department Service Rules, 1997)',
     'notification',2009,'SO(R-III) (S&GAD)/1-24/2007',
     jsonb_build_array(
       'page 5 opens, below the white space after the 2011 notification''s signature (page 4, MUHAMMAD ILLYAS), a new heading GOVERNMENT OF THE PUNJAB / SERVICES AND GENERAL ADMINISTRATION DEPARTMENT / (REGULATIONS WING)',
       'its own date ''Dated Lahore, the 28th October, 2009'', NOTIFICATION, number and enabling formula (Section 23 of the Punjab Civil Servants Act, 1974)',
       'its caption AMENDMENTS adds the Schedule entry at Sr. No. 1-B; it is signed on page 6 by JAVAID ASLAM, ADDITIONAL CHIEF SECRETARY'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc691-p5.png',
     '2bc039bb4698f2767b054351ecfc16a324701c0f770a65098cd20a09a49ad534'),
    (29768::bigint,6,
     'S&GAD (Regulations Wing) Notification No. SOR-III (S&GAD)/1-9/2000 dated 13 September 2007 (amending the Environment Protection Department Service Rules, 1997)',
     'notification',2007,'SOR-III (S&GAD)/1-9/2000',
     jsonb_build_array(
       'page 6 prints, after the 2009 notification''s ''BY ORDER OF THE GOVERNOR OF THE PUNJAB / JAVAID ASLAM / ADDITIONAL CHIEF SECRETARY'', a new heading GOVERNMENT OF THE PUNJAB / SERVICES AND GENERAL ADMINISTRATION DEPARTMENT / (REGULATIONS WING)',
       'its own date ''Dated Lahore, the 13th September, 2007'', NOTIFICATION, number No. SOR-III (S&GAD)/1-9/2000 and enabling formula',
       'its AMENDMENTS paragraphs (1)-(3) run to page 8, signed NAGUIB ULLAH MALIK, ADDITIONAL CHIEF SECRETARY'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc691-p6.png',
     '78d0623e80dd10566fdbe5966b63ae1cee99d37332d25b4a423ee0b6b009cc19'),
    (29847::bigint,8,
     'The Environment Protection Department Service Rules, 1997',
     'rules',1997,NULL::text,
     jsonb_build_array(
       'page 8 prints, after the 2007 notification''s signature, the heading GOVERNMENT OF THE PUNJAB, continued on page 9: SERVICES AND GENERAL ADMINISTRATION & INFORMATION DEPARTMENT, ''The 28th November, 1997'', NOTIFICATION No. SOR-III.1-26/87',
       'the Governor of the Punjab ''is pleased to make the following rules, namely:-'' and the recruitment table follows, rows 1-35 (pages 9-14), signed TARIQ SAEED HAROON',
       'the three amending notifications before it name these rules the Environment Protection Department Service Rules, 1997'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc691-p8.png',
     'c73cdf12b812ebdc07131524d24a275e7b2262893f1711a0cff8b91f140de43b')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2036,691,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-691.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-06-c.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8,9,10,11,12,13,14),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 29735 THEN 'Block 29735 begins the S&GAD notification of 28 October 2009 adding Sr. No. 1-B to the Schedule of the Environment Protection Department Service Rules, 1997 -- a separate amending instrument, not part of the 2011 notification printed before it (owner decision 2026-10-06, q3 split-four).'
         WHEN 29768 THEN 'Block 29768 begins the S&GAD notification of 13 September 2007 amending the Schedule of the Environment Protection Department Service Rules, 1997 -- a separate amending instrument (owner decision 2026-10-06, q3 split-four).'
         ELSE 'Block 29847 begins the notification of 28 November 1997 making the Environment Protection Department Service Rules, 1997 -- the principal instrument the three earlier-printed notifications amend (owner decision 2026-10-06, q3 split-four).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-691.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-06-c.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=691 AND c.source_observation_id=2036
   AND c.start_block_id IN (29735,29768,29847)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
