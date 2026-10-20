-- Source-verified boundary evidence for the reviewed split of Punjab document 1822
-- (tools/evidence/multi-instrument-plans/doc-1822.json).  Drafted by agent CK (8 Oct 2026, prepare mode);
-- renamed without -DRAFT and applied by builder BZ on 8 Oct 2026.
--
-- The official PDF (observation 2196, catalogued as 'ENVIRONMENTAL TRIBUNAL RULES, 1999') prints three
-- instruments: pages 1-5 the Environmental Tribunal Rules, 1999 (contents, the S.R.O.(1)/2001 notification,
-- rules 1-18, Schedules 1-III); pages 5-6 the Ministry of Law, Justice and Human Rights notification
-- S.R.O.(1)/89 of 2 June 1999 establishing the Environmental Protection Tribunals (with its two-row table);
-- page 6 the separate notification No.F.22(1)/97-A,III(A) of 2 June 1999 appointing the Chairpersons, followed
-- (pp6-7) by its forwarding and the 18-item 'Copy to' distribution list, which is apparatus and part of no
-- instrument.  The owner decided this on 2026-10-08 (decision-review-2026-10-08-h.json, doc 1822 q1 'other',
-- note: three instruments).  The Rules open the document at block 122459, so they need no boundary row; the
-- establishing notification (block 122543, p5) and the appointing notification (block 122558, p6) do.
-- Doc 268 / 691 precedent: tools/evidence/split-doc-268-boundaries.sql, split-doc-691-boundaries.sql.
--
-- This file appends evidence only.  Materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 1822`.  Run it while the single-tree instrument
-- (677d65d8-e946-41a8-a185-8255535a5398 on 8 Oct) is still active: the candidates are keyed to it.
-- The readings (claude/agCK/patch-1822.json) need only rules already in segment.py
-- (unnumbered_root_provision, printed_heading_extent; pin claude/agCK/pin-1822.json).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1822 AND i.source_observation_id=2196
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (122543::bigint,5,
     'Ministry of Law, Justice and Human Rights Notification S.R.O.(1)/89 dated 2 June 1999 (establishing the Environmental Protection Tribunals)',
     'notification',1999,'S.R.O.(1)/89',
     jsonb_build_array(
       'page 5 prints, after the Rules'' last heading SCHEDULE III [See Rule 16(2)(iii)] FEES FOR APPEALS and blank space, a new heading GOVERNMENT OF PAKISTAN / MINISTRY OF LAW, JUSTICE AND HUMAN RIGHTS (block 122543)',
       'its own date ''[2nd June, 1999]'' (block 122544) and caption NOTIFICATION (block 122545)',
       'its operative paragraph ''S.R.O.(1)/89:- In exercise of the powers conferred by Section 20(1) of the Pakistan Environmental Protection act, 1997, the Provincial Government is pleased to establish Environmental Protection Tribunal in the country ... as set-out in the table:-'' (block 122546) and the table S. No. | Name of Tribunal | Tribunal Limit | Place of Sitting, rows 1 (Lahore) and 2 (Karachi) on page 6',
       'it is a different instrument from the Rules: a different ministry (the Rules are notified by the Ministry of Environment, Local Government and Rural Development), its own date and number, and its own enabling provision (section 20(1) of the Act, not section 33); owner decision q1'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p5.png',
     'c79db00cd72a2007e75105bf4693cba3ad0de2bb500fd535512adf332a35bd05'),
    (122558::bigint,6,
     'Ministry of Law, Justice and Human Rights Notification No. F.22(1)/97-A,III(A) dated 2 June 1999 (appointing the Chairpersons of the Environmental Protection Tribunals)',
     'notification',1999,'F.22(1)/97-A,III(A)',
     jsonb_build_array(
       'page 6 prints, after the first notification''s table, its file number No.F.22(1)/97-A.III and the forwarding to the Manager, Printing Corporation of Pakistan Press, a new heading GOVERNMENT OF PAKISTAN / MINISTRY OF LAW, JUSTICE AND HUMAN RIGHTS (block 122558)',
       'its own date ''[2nd June, 1999]'' (block 122559) and caption NOTIFICATION (block 122560)',
       'its operative paragraph ''No.F.22(1)/97-A,III(A)The Federal Government is pleased to appoint the following to be the Chairperson''s Environmental Protection Tribunals, with immediate effect and until further orders, in addition to their own duties:-'' (block 122561) and the table S.NO. | NAME OF THE CHAIR PERSON | NAME OF TRIBUNAL, rows 1 (Justice Sh. Amjad Ali) and 2 (Justice (R) Abdul Rehman)',
       'the owner decided it is a third instrument, separate from the establishing notification (q1); its forwarding, ''Copy to:-'' and the distribution list 1-18 (pp6-7) are apparatus inside its span, set aside by the reviewed readings'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p6.png',
     'efc63c2489a817abc52a2929e0dcd190baf6ed1293fdf4ed6cff94d9fa978487')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2196,1822,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1822.json',
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
         WHEN 122543 THEN 'Block 122543 begins the Ministry of Law, Justice and Human Rights notification S.R.O.(1)/89 of 2 June 1999 establishing the Environmental Protection Tribunals -- a separate instrument, not part of the Environmental Tribunal Rules, 1999 printed before it (owner decision 2026-10-08, q1).'
         ELSE 'Block 122558 begins the separate Ministry of Law, Justice and Human Rights notification No.F.22(1)/97-A,III(A) of 2 June 1999 appointing the Chairpersons of the Environmental Protection Tribunals -- a third instrument (owner decision 2026-10-08, q1).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1822.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1822 AND c.source_observation_id=2196
   AND c.start_block_id IN (122543,122558)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
