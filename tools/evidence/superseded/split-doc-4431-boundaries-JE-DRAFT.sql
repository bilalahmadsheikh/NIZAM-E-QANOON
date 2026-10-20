-- DRAFT by agent JE (13 Oct 2026, prepare mode; not run). Source-verified boundary evidence for the reviewed split of
-- document 4431 (tools/evidence/multi-instrument-plans/doc-4431-DRAFT.json). Pattern: split-doc-4378-boundaries.sql.
--
-- Observation 2734 (The Punjab Mining Concession Rules, 2002), 114 pages.
-- Owner decision: decision-review-2026-10-12-k.json, document 4431, q3 'split' -- the 2004 auction notification (with
-- Annex A) and the 2003 amending notification each become a separate instrument; the Rules end at p98.
--
-- Read from the renders (agent JE): p98 (00073cdb...) Schedule 3 'E. BASE METALS GROUP', its NOTE and page number 95
-- (block 787334) -- the Rules end; p99 (313033ae...) 'GOVERNMENT OF THE PUNJAB / MINES & MINERALS DEPARTMENT / Dated
-- Lahore, the 27th October, 2004 ... Notification ...' (block 787335); p103 (4aa25eb1...) the end of the 2004
-- notification's Annex-"A" ('Undercutting machine, pumps, etc.', block 787365), then 'THE PUNJAB GAZETTE / PUBLISHED
-- BY AUTHORITY / LAHORE TUESDAY, MAY 06, 2003' (block 787366) and the 30 April 2003 notification; p108 (98cecc10...)
-- amendment 31 and the Secretary's signature, then the Directorate's covering letters; p112 (0c24e369...) the 9 May
-- 2003 fee notification (card claude/agJE/card-4431-q5.json); p114 (19818da2...) its endorsements.
--
-- ORDER: rename the plan, record claude/agJE/patch-4431.json (needs rules reviewed_printed_rule_opener,
-- reviewed_set_aside_unit, reviewed_list_item_text item_kind variant, reviewed_text_unit -- $S/agJE-rule8.py chain),
-- pin unreleased-v4, then this file, then `tools/materialize_multi_instrument.py --document 4431` (dry run first).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=4431 AND i.source_observation_id=2734
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (787335::bigint,99,'Notification No. SOT (M&MD) 8-15/90(Voll) of 27 October 2004','notification',2004,'SOT (M&MD) 8-15/90(Voll)',
     jsonb_build_array(
       'page 98 ends the Rules with Schedule 3''s NOTE and the page number 95',
       'page 99 opens GOVERNMENT OF THE PUNJAB / MINES & MINERALS DEPARTMENT / Dated Lahore, the 27th October, 2004 and a notification laying down financial qualifications and terms for six rock-salt mining leases by open auction under rule 187',
       'its Annex-"A" DETAILS OF MACHINERY & EQUIPMENT ends on page 103'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4431-p99.png',
     '313033ae197e1b139dd350385d7d80f58ddf8bf3164440062dd7058d2b0d9b97'),
    (787366::bigint,103,'Notification No. V(I&MD)3-21/95 Vol-III of 30 April 2003','notification',2003,'V(I&MD)3-21/95 Vol-III',
     jsonb_build_array(
       'page 103 prints, after the 2004 Annex-"A", THE PUNJAB GAZETTE / PUBLISHED BY AUTHORITY / LAHORE TUESDAY, MAY 06, 2003',
       'then GOVERNMENT OF THE PUNJAB / INDUSTRIES, MINES AND MINERALS DEPARTMENT / Dated Lahore, the 30th April, 2003 / NOTIFICATION No.V(I&MD)3-21/95Vol-III directing amendments to the Punjab Mining Concession Rules, 2002',
       'its amendments 1-31 run to page 108'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4431-p103.png',
     '4aa25eb10b3a701c260932492531f4185e511569b9d0aeb11c4266034d094c62')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2734,4431,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4431.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-k.json',
         'question_id','q3',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(98,99,103,108,112,114),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 787335 THEN 'Block 787335 begins the 27 October 2004 auction notification bound after the Rules (owner decision 2026-10-12 export k q3 split).'
         ELSE 'Block 787366 begins the Punjab Gazette of 6 May 2003 with the 30 April 2003 amending notification (owner decision 2026-10-12 export k q3 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4431.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-k.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=4431 AND c.source_observation_id=2734
   AND c.start_block_id IN (787335,787366)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
