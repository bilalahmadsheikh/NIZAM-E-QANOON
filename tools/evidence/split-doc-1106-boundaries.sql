-- Source-verified boundary evidence for the reviewed split of Punjab document 1106
-- (tools/evidence/multi-instrument-plans/doc-1106.json).  Drafted by agent CC; renamed from -DRAFT and
-- applied by builder BZ on 2026-10-08 after the rules below were ported.
--
-- The official PDF (observation 2050) prints two instruments: pages 1-11 the
-- S&GA&I Department notification of 13 April 1996 making the Directorate of
-- Floriculture (Training & Research), Punjab, Lahore Services Rules, 1996
-- (rules 1-3 and the annexed recruitment Schedule, pp2-11), and pages 12-15
-- the notification of 30 April 1998 making the Directorate of Floriculture
-- (T&R) (Ministerial Posts) Services Rules, 1998 (rules 1-3 and its own
-- Schedule, pp13-15).  The owner decided this on 2026-10-07
-- (decision-review-2026-10-07-e.json, doc 1106 q1 'split', q2 'artefact',
-- q3 'rows-by-group').  The 1996 notification opens the document at block
-- 52922, so it needs no boundary row; the 1998 notification does, at block
-- 53117 (page 12's heading 'GOVERNMENT OF THE PUNJAB / SERVICES GENERAL
-- ADMINISTATION & ...').  Doc 268 / 691 precedent:
-- tools/evidence/split-doc-268-boundaries.sql, split-doc-691-boundaries.sql.
--
-- DIFFERENT FROM 268 / 691: this observation is ALREADY materialised as two
-- expressions by the legacy PRIMARY_DOCUMENTS path (detector candidate
-- 23080cf7-728d-40fe-bab1-97b9f427f1a8 at block 53120, cited by the active
-- manifest but no longer present in segmentation_boundary_candidate).  That
-- split started the 1998 expression at the enabling formula (53120), leaving
-- page 12's heading, NOTIFICATION and date (53117-53119) in the 1996
-- expression.  So (1) the candidate below is keyed to the ACTIVE PRIMARY
-- expression (expression_ordinal 0), not to a single-tree instrument, and
-- (2) it anchors at 53117, the plan's span start.  Before materialising, the
-- lead must take 1106 out of PRIMARY_DOCUMENTS in
-- tools/materialize_multi_instrument.py (prepare() refuses a document with
-- both a plan and a legacy listing) and rename the plan to doc-1106.json.
--
-- This file appends evidence only.  Materialisation is the separate,
-- dry-run-gated `tools/materialize_multi_instrument.py --document 1106`.
-- The readings (claude/agCC/patch-1106.json) need two parser rules that do not
-- exist yet (schedule_group_caption, uncontented_subpart_scan_schedule_bound),
-- an extension of named_schedule_row (rows nest under an open caption) and its
-- choice gate admitting 'rows-by-group' (see claude/agCC-log.md, doc 1106):
-- do not materialise before they exist.

\set ON_ERROR_STOP on
BEGIN;

WITH active_primary AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1106 AND i.source_observation_id=2050
     AND i.is_active AND i.duplicate_of IS NULL
     AND i.expression_ordinal=0 AND i.expression_role='primary'
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (53117::bigint,12,
     'Directorate of Floriculture (T&R) (Ministerial Posts) Services Rules, 1998',
     'rules',1998,NULL::text,
     jsonb_build_array(
       'page 12 opens, after the 1996 Schedule ends on page 11 (row 33 Cleaner), a new heading GOVERNMENT OF THE PUNJAB / SERVICES GENERAL ADMINISTATION & / INFORMATION DEPARTMENT (blocks 53117-53118)',
       'its own NOTIFICATION dated ''The 30th April, 1998'' (block 53119) and enabling formula ''No. SOR-III-1-3/96. In exercise of the powers conferred on him by Section 23 of the Punjab Civil Servants Act, 1974 ... pleased to make the following rules, namely : -'' (block 53120)',
       'rule 1 names it: ''These Rules may be called the Directorate of Floriculture (T&R) (Ministerial Posts) Services Rules, 1998'' (block 53121); rule 3 annexes its own Schedule (pages 13-15)',
       'it is authenticated BY ORDER OF THE GOVERNOR OF THE PUNJAB, TARIQ SAEED HAROON, and forwarded under a line dated 17th April, 1996 (sic, a source anomaly kept as printed)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1106-p12.png',
     'b10423e420a47acc5fcc285deebb7ce55b4a4e280a517f4db54d09dbc321f840')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2050,1106,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1106.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-07-e.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8,9,10,11,12,13,14,15),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256,
         'supersedes_detector_anchor',jsonb_build_object(
           'candidate_id','23080cf7-728d-40fe-bab1-97b9f427f1a8','start_block_id',53120,
           'note','the legacy split began the 1998 expression at its enabling formula; page 12 prints its heading, NOTIFICATION and date at 53117-53119'))
  FROM active_primary a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block 53117 begins the S&GA&I Department notification of 30 April 1998 making the Directorate of Floriculture (T&R) (Ministerial Posts) Services Rules, 1998 -- a separate instrument with its own rules 1-3 and annexed Schedule, not part of the 1996 Rules printed before it (owner decision 2026-10-07, q1 split).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1106.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-07-e.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1106 AND c.source_observation_id=2050
   AND c.start_block_id=53117
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
