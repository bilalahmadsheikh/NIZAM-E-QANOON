-- Source-verified boundary evidence for the reviewed split of Punjab document 1626
-- (tools/evidence/multi-instrument-plans/doc-1626.json).  Drafted by agent CJ (prepare mode); renamed
-- without the draft suffix and applied by builder BZ on 9 Oct 2026 after rules U and V were ported.
--
-- The official PDF (observation 2055, catalogued as 'PUNJAB FOOD DEPARTMENT (EXECUTIVE AND MINISTERIAL
-- POSTS) RECRUITMENT RULES 1993') is a compilation: p1 a compiler's index; pp2-11 the S&GA&I notification
-- No.SOR-III-2-9/85 of 14 April 1993 making the Punjab Food Department (Executive and Ministerial Posts)
-- Recruitment Rules 1993 (rules 1-4 and the Schedule); pp12-13 an unrelated page of THE PUNJAB WEEKLY GAZETTE
-- MAY 26, 1993; p14 the amending notification of 25 February 1994; pp15-16 the amending notification of
-- 8 September 1998; p17 the corrigendum of 25 January 1994; p18 the amending notification of 23 January 2001;
-- pp19-21 the amending notification of 8 April 2009.  The owner decided this on 2026-10-08
-- (decision-review-2026-10-08-h.json, doc 1626 q1 'split', q2 'rows-by-group', q3 'keep-both').
--
-- Every expression needs an anchor: the principal Rules do NOT open the document (p1 and p2's 'TEXT' box
-- are compiler front matter outside every span), so block 101078 needs a confirmed_split too (doc 691
-- precedent: its 1997 Rules at p8).  pp12-13 (blocks 101255-101286) and 101073-101077 are in no expression.
-- Candidates are keyed to the ACTIVE single-tree instrument; run while it is still active.
--
-- This file appends evidence only.  Materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 1626`.  The readings (claude/agCJ/patch-1626.json)
-- need rule U `half_paren_clause_label` (new key source_half_paren_clause_blocks) and extension V
-- `order_suffix_one_block` (claude/agCJ-log.md, $S/agCJ-rule.py): do not materialise before they exist.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1626 AND i.source_observation_id=2055
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (101078::bigint,2,
     'Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993',
     'rules',1993,NULL::text,
     jsonb_build_array(
       'page 1 is a compiler''s index (CONTENTS: NOTIFICATION 2 ... AMENDMENTS 19), and page 2 opens with the compiler''s boxed caption TEXT (block 101077)',
       'the title ''Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993'' (blocks 101078-101079), ''[14th April, 1993]'', NOTIFICATION and ''No.SOR-III-2-9/85.  In exercise of the powers conferred on him under Section 23 of the Punjab Civil Servants Act, 1974 ... rules, namely:-'' (block 101080)',
       'rules 1-4 follow (rule 1 names the Rules) and the ten-column SCHEDULE runs pp3-11 (Food Directorate rows 1-29, Divisional/District Estt rows 1-20)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p2.png',
     'c51a1111d1f14d7428d4095b5ce3b34b5900fda535f24847ee9176af4de6d999'),
    (101287::bigint,14,
     'S&GA&I Department Notification No. SOR-III-2-9/85 dated 25 February 1994 (amending the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993)',
     'notification',1994,'SOR-III-2-9/85',
     jsonb_build_array(
       'page 14 opens, after the unrelated Gazette pages 12-13, a new heading GOVERNMENT OF THE PUNJAB / SERVICES, GENERAL ADMINISTRATION & INFORMATION DEPARTMENT (blocks 101287-101288)',
       'its own NOTIFICATION, ''Dated 25th February, 1994.'' and ''No.SOR-III-2-9/85. ... the following further amendment shall be made, namely:-''',
       'A M E N D M E N T.: Sr No.5 (Food Directorate) columns 3, 5 and 7-9 substituted; BY ORDER OF THE GOVERNOR OF PUNJAB / NAZIR AHMAD CHAUDHRY'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p14.png',
     '0aee79581aa15f4e6cabf1542ef6da77511adfdf6f7a4def5de6ea7099df28c0'),
    (101297::bigint,15,
     'S&GA&I Department Notification dated 8 September 1998 (amending the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993)',
     'notification',1998,NULL::text,
     jsonb_build_array(
       'page 15 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES GENERAL ADMINISTRATION AND INFORMATION DEPARTMENT (blocks 101297-101298) and N O T I F I C A T I O N',
       '''Dated Lahore, the 08th September, 1998'' and ''---------1994 In experience of the powers conferred ... the following amendments shall be made namely:-'' (no number printed)',
       'A M E N D M E N T S.: entries 21-25 added after serial No.20 (Divisional/District Establishment), pp15-16; signed TARIQ SAEED HARCON with a distribution list 1-6'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p15.png',
     '58246130c4a5fda23201f5c17c23862de6948f7101308117187f6effb6b1340b'),
    (101338::bigint,17,
     'S&GA&I Department Corrigendum, Endst No. SOR-2-9/85 dated 25 January 1994 (to the Schedule of the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993)',
     'notification',1994,'SOR-2-9/85',
     jsonb_build_array(
       'page 17 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES, GENERAL ADMINISTRATION & INFORMATION DEPARTMENT (blocks 101338-101339) and the caption CORRIGENDUM',
       'it corrects the 1993 Schedule: under the functional unit ''Divisional/District Establishment'' against Serial No.15 in column 3 ''Assistant Food Controller'' for ''Assistant Controller''',
       'its only number and date are the endorsement''s: ''Endst No.SOR-2-9/85, Dated 25th January, 1994'' (block 101343)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p17.png',
     '46cc5f0169efdbcade196beabaa98f40ad224f5a4c12f42696ca8a8a65e1587d'),
    (101348::bigint,18,
     'S&GA&I Department Notification No. SOR-III-1-9/94 dated 23 January 2001 (amending the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993)',
     'notification',2001,'SOR-III-1-9/94',
     jsonb_build_array(
       'page 18 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES, GENERAL ADMINISTRATION & INFORMATION DEPARTMENT (blocks 101348-101349)',
       'NOTIFICATION ''Dated 23rd January, 2001.'' and ''No.SOR-III-1-9/94. ... the following amendment shall be made, namely:-''',
       'A M E N D M E N T.: Sr No.12 column 7 substituted (i)-(iv); signed (TARIQ FAROOQ), endorsement of 25 January 2001'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p18.png',
     '4f96d914cd7d5c632f756bbb0cc532e87c4139631a4cfe0d18c649df96f3268c'),
    (101362::bigint,19,
     'S&GAD Notification No. SOR-III(S&GAD)1-17/2001 dated 8 April 2009 (amending the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993)',
     'notification',2009,'SOR-III(S&GAD)1-17/2001',
     jsonb_build_array(
       'page 19 opens a new heading GOVERNMENT OF THE PUNJAB / SERVICES GENERAL ADMINISTRATION AND INFORMATION DEPARTMENT (blocks 101362-101363) and N O T I F I C A T I O N',
       '''Dated Lahore, the 08th April, 2009'' and ''No.SOR-III(S&GAD)1-17/2001. ... the following further amendments shall be made:-''',
       'A M E N D M E N T S.: 1. Sr No.2, 4 & 12 columns 7-10 substituted; 2 Sr No.25 columns 3, 5, 7 & 9 substituted (pp19-21); signed JAVAID ASLAM, endorsement of 14 April 2009'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1626-p19.png',
     '71ceccb6962213da8b114ac61f4973df649157d3a0836439ca8eac8d2a35a19a')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2055,1626,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1626.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 101078 THEN 'Block 101078 begins the Punjab Food Department (Executive and Ministerial Posts) Recruitment Rules 1993 (notification of 14 April 1993, rules 1-4 and the Schedule) -- the principal instrument of the compilation; p1 and the p2 TEXT box before it are compiler front matter (owner decision 2026-10-08, q1 split).'
         WHEN 101287 THEN 'Block 101287 begins the S&GA&I notification of 25 February 1994 amending the Schedule of the 1993 Rules (Sr No.5) -- a separate amending instrument; pp12-13 before it are unrelated Gazette material (owner decision 2026-10-08, q1 split).'
         WHEN 101297 THEN 'Block 101297 begins the S&GA&I notification of 8 September 1998 adding entries 21-25 to the Schedule of the 1993 Rules -- a separate amending instrument (owner decision 2026-10-08, q1 split).'
         WHEN 101338 THEN 'Block 101338 begins the S&GA&I corrigendum (Endst No.SOR-2-9/85 of 25 January 1994) correcting Serial No.15 of the 1993 Schedule -- a separate amending instrument (owner decision 2026-10-08, q1 split).'
         WHEN 101348 THEN 'Block 101348 begins the S&GA&I notification of 23 January 2001 substituting column 7 of Sr No.12 of the 1993 Schedule -- a separate amending instrument (owner decision 2026-10-08, q1 split).'
         ELSE 'Block 101362 begins the S&GAD notification of 8 April 2009 substituting entries of Sr No.2, 4, 12 and 25 of the 1993 Schedule -- a separate amending instrument (owner decision 2026-10-08, q1 split).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1626.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-08-h.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1626 AND c.source_observation_id=2055
   AND c.start_block_id IN (101078,101287,101297,101338,101348,101362)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
