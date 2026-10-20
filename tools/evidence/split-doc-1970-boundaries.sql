-- Source-verified boundary evidence for the reviewed split of Punjab document 1970
-- (tools/evidence/multi-instrument-plans/doc-1970.json).  Drafted by agent CL; renamed without the draft
-- suffix and applied by builder BZ on 9 Oct 2026.
--
-- The official PDF (observation 2415, catalogued as 'CHILDREN LIBRARY COMPLEX,
-- LAHORE RECRUITMENT RULES, 1991') prints pages 1-4 the Rules (contents rows
-- 1-8, the Board's notification No.86(PIMP.)12-60/89, rules 1-7, signed 6 July
-- 1991), page 5 the Education Department notification of 18 January 1998
-- re-constituting the Board of Governors, page 6 the notification of 23
-- September 1990 constituting it, and page 7 a third notification of 22
-- September 1990 notifying the Complex as an institution under the Punjab
-- Educational and Training Institutions Ordinance, 1960.  The owner decided on
-- 2026-10-08 (decision-review-2026-10-08-h.json, doc 1970 q1 'split') that the
-- 1990 and 1998 notifications each become a separate instrument; the card named
-- pp5-6 only; the owner confirmed on 8 Oct 2026 (chat, logged) that the p7 notification
-- (block 141251, plan ordinal 3) is its own instrument too.  The Rules
-- open the document at block 141169, so they need no boundary row.
--
-- Doc 691 precedent: tools/evidence/split-doc-691-boundaries.sql.  This file
-- appends evidence only; materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 1970`, run while the
-- single-tree instrument is still active.  It needs the agCL rules
-- blank_rule_heading_none, root_provision_member_list and
-- numeric_quote_definition_cut (claude/agCL-log.md) before it is run.
--
-- A byte-identical second observation (2846, instrument 23d22b4c..., duplicate_of
-- the canonical 0ff38d86...) exists for this document; the plan machinery
-- materialises the canonical observation only (see claude/agCL-log.md).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1970 AND i.source_observation_id=2415
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (141232::bigint,5,
     'Education Department Notification No. SO(PI)12-83/89(P) dated 18 January 1998 (re-constituting the Board of Governors of the Children Library Complex, Lahore)',
     'notification',1998,'SO(PI)12-83/89(P)',
     jsonb_build_array(
       'page 4 ends the Rules with rule 7, ''BY ORDER OF THE BOARD OF GOVERNORS'', ''Dated: Lahore, the 6th July, 1991.'' and AMIN ULLAH CHAUDHRY, EDUCATION SECRETARY, the rest of the page blank',
       'page 5 opens a new heading GOVERNMENT OF THE PUNJAB / EDUCATION DEPARTMENT, NOTIFICATION, No.SO(PI)12-83/89(P), by which the Governor of the Punjab ''is pleased to re-constitute the following Board of Governor of Children Library Complex, Lahore'', members 1)-13)',
       'signed SHAHZAD QASIER, EDUCATION SECRETARY, ''Dated Lahore, the 18th January, 1998'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1970-p5.png',
     'f761e4ab5bd2fb0fd5001f49923439f7f49a6d220b1ba12fd24c49728a85e0de'),
    (141242::bigint,6,
     'Education Department Notification No. SO(P.IMP)12-38/89 dated 23 September 1990 (constituting the Board of Governors for the Children Library Complex, Lahore)',
     'notification',1990,'SO(P.IMP)12-38/89',
     jsonb_build_array(
       'page 6 opens a new heading GOVERNMENT OF THE PUNJAB / EDUCATION DEPARTMENT, NOTIFICATION, No.SO(P.IMP)12-38/89',
       'the Governor of the Punjab ''is pleased to constitute the following Board of Governor for the Children Library Complex, Lahore with immediate effect:'', members 1-12',
       '''BY ORDER OF THE GOVERNOR OF THE PUNJAB.'' and ''Dated: Lahore the 23rd Sept: 1990.'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1970-p6.png',
     '2193ee507f9148029c2c76e0fb7cefc58c441143c387c4010e6b5381ff59fad0'),
    -- owner confirmed 8 Oct 2026 (chat, logged; not in the export -h q1 card)
    (141251::bigint,7,
     'Education Department Notification No. So(P.IMP)12-83/89 dated 22 September 1990 (notifying the Children Library Complex, Lahore as an institution under the Punjab Educational and Training Institutions Ordinance, 1960)',
     'notification',1990,'So(P.IMP)12-83/89',
     jsonb_build_array(
       'page 7 opens a new heading GOVERNMENT OF THE PUNJAB / EDUCATION DEPARTMENT, NOTIFICATION, No.So(P.IMP)12-83/89',
       'one paragraph: the Governor of the Punjab ''is pleased to notify the Children Library Complex, Lahore as an institution for the purpose of the Ordinance'' and directs that the Ordinance shall apply to it',
       '''Dated: Lahore, the 22nd SEPT: 1990'', ''BY ORDER OF THE GOVERNOR OF THE PUNJAB.'', ''SECRETARY TO GOVERNOR OF THE PUNJAB, EDUCATION DEPARTMENT'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1970-p7.png',
     '089873c6aef7b6ce19bdb0b008d035a0f856dbd27ac07659861ebeb4d8e6f98a')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2415,1970,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1970.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
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
         WHEN 141232 THEN 'Block 141232 begins the Education Department notification of 18 January 1998 re-constituting the Board of Governors of the Children Library Complex, Lahore -- a separate instrument bound after the 1991 Rules (owner decision 2026-10-08, export -h q1 split).'
         WHEN 141242 THEN 'Block 141242 begins the Education Department notification of 23 September 1990 constituting the Board of Governors for the Children Library Complex, Lahore -- a separate instrument (owner decision 2026-10-08, export -h q1 split).'
         ELSE 'Block 141251 begins the Education Department notification of 22 September 1990 notifying the Children Library Complex, Lahore as an institution under the 1960 Ordinance -- a separate instrument (owner confirmed 8 Oct 2026, chat, logged: the export -h q1 card named pp5-6 only).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1970.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1970 AND c.source_observation_id=2415
   AND c.start_block_id IN (141232,141242,141251)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
