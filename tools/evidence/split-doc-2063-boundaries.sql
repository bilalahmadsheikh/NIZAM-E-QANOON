-- Source-verified boundary evidence for the reviewed split of Sindh document 2063
-- (tools/evidence/multi-instrument-plans/doc-2063.json).  Drafted by agent CQ (10 Oct 2026, prepare mode);
-- renamed without the draft suffix and applied by builder BZ on 10 Oct 2026.
--
-- The official PDF (observation 4667, catalogued as 'Sindh Development and Maintenance of Infrastructure [Cess]
-- Rules, 1994') prints two instruments: pages 1-4 the Rules (notification NO:SO(TAXES) E&T/2(41)94 of 22 August
-- 1994, rules 1-14, signature, and on p4 the forwarding and distribution list); pages 5-6 the Excise & Taxation
-- Department notification NO.SO(TAXES)E&T/2(83)03 of 28 June 2010 substituting sub-rule (2) of rule 14, with its
-- own signature and (p6) forwarding and distribution list.  The owner decided this on 2026-10-10
-- (decision-review-2026-10-10-i.json, doc 2063 q1 'split': "the 2010 notification becomes a separate instrument
-- whose text is the substituted rule 14(2)").  The Rules open the document at block 153766, so they need no boundary
-- row; the 2010 notification (block 153844, p5) does.
-- Doc 268 / 691 / 1822 precedent: tools/evidence/split-doc-268-boundaries.sql, split-doc-1822-boundaries.sql.
--
-- This file appends evidence only.  Materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 2063`.  Run it while the single-tree instrument
-- (dc4ef4ec-ff0c-4682-a383-a8f7b534a061 on 10 Oct) is still active: the candidates are keyed to it.
-- The readings (claude/agCQ/patch-2063.json) need only rules already in segment.py (pin claude/agCQ/pin-2063.json).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=2063 AND i.source_observation_id=4667
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (153844::bigint,5,
     'Excise and Taxation Department Notification No. SO(TAXES)E&T/2(83)03 dated 28 June 2010 (amending rule 14 of the Sindh Development and Maintenance of Infrastructure Cess Rules, 1994)',
     'notification',2010,'SO(TAXES)E&T/2(83)03',
     jsonb_build_array(
       'page 4 ends the Rules'' forwarding with ''( ASADULLAH MEMON ) SECTION OFFICER (TAXES)'' and the rest of the page blank; page 5 opens with a new head GOVERNMENT OF SINDH / EXCISE & TAXATION DEPATRTMENT (block 153844)',
       'its own date ''Karachi, dated 28th June, 2010'' (block 153845) and caption NOTIFICATION (block 153846)',
       'its own number and enabling formula ''NO.SO(TAXES)E&T/2(83)03. In exercise of the powers conferred by section 10 of the Sindh Finance Act, 1994, the Government of Sindh is pleased to make the following amendment in the Sindh Development and Maintenance of Infrastructure Cess Rules, 1994:-'' (blocks 153847-153849)',
       'its operative text ''AMENDMENT / In rule 14:- / For sub-rule (2), the following shall be substituted:- / 2. Government may by Notification, for the reasons to be recorded exempt from payment of Cess to:- a. ... e. ...'' (blocks 153850-153858), its own signature (block 153859) and, on page 6, its own forwarding NO. SO(TAXES)E&T/2(83)/1659 and six-item distribution list (blocks 153861-153863)',
       'it is a different instrument from the Rules: a 2010 amending notification with its own date, number and signature, sixteen years after the 1994 Rules; owner decision q1 ''split'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc2063-p5.png',
     'e8b0e5e84c163ae9bfd0e482d5a324b2a705938e5fbcf7b1e816b1a7e0a85be7')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,4667,2063,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-2063.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block 153844 begins the Excise and Taxation Department notification NO.SO(TAXES)E&T/2(83)03 of 28 June 2010 substituting sub-rule (2) of rule 14 -- a separate, amending instrument, not part of the Sindh Development and Maintenance of Infrastructure [Cess] Rules, 1994 printed before it (owner decision 2026-10-10, q1 split).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-2063.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-10-i.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=2063 AND c.source_observation_id=4667
   AND c.start_block_id IN (153844)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
