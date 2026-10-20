-- Source-verified boundary evidence for the reviewed split of Punjab document 1973
-- (tools/evidence/multi-instrument-plans/doc-1973.json).  Drafted by agent CK (10 Oct 2026, prepare mode);
-- renamed (with the plan) without the draft suffix and applied by builder BZ on 10 Oct 2026, after migration
-- 0063 and the builder-side undated changes.
--
-- The official PDF (observation 2341, catalogued as 'THE PUNJAB EXCISE POWERS AND APPEAL ORDERS', stored year
-- 1975) is a departmental compilation of six instruments (owner decision 2026-10-08,
-- decision-review-2026-10-08-h.json doc 1973 q1 'other'; 2026-10-10 decision-review-2026-10-10-i.json q3-q5):
--   E0 (blocks 141488-141493 + 141495-141554, pp1-7) the Punjab Excise Powers and Appeal Orders, 1932 -- opens the
--      document, no boundary row;
--   E1 (141494 p2 + 141562-141564 p10) the Excise and Taxation Department notification No.52-75/26-EX (P)I of
--      7 January 1975 -- p2 block 141494 (after the reading that moves 3.1's opening words to block 141495);
--      the p10 reprint is a duplicate reproduction set aside by the readings;
--   E2 (141555-141557, pp7-8) the North West Frontier Province Excise Powers and Appeal Orders (notification of
--      30 March 1933) -- block 141555 (after the reading that moves 3.19's heading and formula into it);
--   E3, E4, E5 (141558, 141559, 141560-141561, pp8-9) three undated West Pakistan notifications (owner q3
--      'undated': detected_year NULL).
-- Doc 268 / 691 / 1106 precedent.  Run while the single-tree instrument (b2db344e-ce8b-43e8-8b66-98c3459cbc0c on
-- 10 Oct) is still active: the candidates are keyed to it.  This file appends evidence only; materialisation is
-- the separate, dry-run-gated `tools/materialize_multi_instrument.py --document 1973`, which needs the seven
-- pending parser rules, the 'number-1' owner-cited choice and the 'undated' change first (claude/agCK-log.md).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=1973 AND i.source_observation_id=2341
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (141494::bigint,2,
     'Punjab Excise and Taxation Department Notification No. 52-75/26-EX (P)I dated 7 January 1975 (appointing the Director General Excise and Taxation as Excise Commissioner)',
     'notification',1975,'52-75/26-EX (P)I',
     jsonb_build_array(
       'page 2 prints, under the compilation heading GOVERNMENT OF THE PUNJAB / EXCISE AND TAXATINO DEPARTMENT / THE PUNJAB EXCISE POWERS AND APPEAL ORDERS, the caption NOTIFICATION, ''[7th Jan 1975]'' and ''No.52-75/26-EX (P)I, dated. III. In exercise of the powers conferred by section 9 of the Punjab Excise Act 1914 ... is pleased to appoint the Director General Excise and Taxation Punjab to be an Excise Commissioner ...'' (block 141494)',
       'paragraph 3.1 of the Punjab Orders follows in the same extracted block; the reviewed reading moves its opening words to block 141495, so the instruments part at a block boundary',
       'page 10 reprints the same notification, signed ABDUL WAHID, Secretary to Government (blocks 141562-141564): a duplicate reproduction (owner q1), set aside',
       'owner decision 2026-10-08 q1: a separate instrument, not a preface to the Punjab Orders'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1973-p2.png',
     '0f96a307d65019c5f98067595c1d66c681ac51af33a886233d7be2f186a5dfdb'),
    (141555::bigint,7,
     'North West Frontier Province Excise Powers and Appeal Orders',
     'order',1933,'3754-EXC-XIA-A-66',
     jsonb_build_array(
       'page 7 prints, after 3.14-3.18 ''Not reproduced being unnecessary.'', ''3.19 North West Frontier Province Government Revenue Department Notification No. 3754-EXC-XIA-A-66 dated Peshawar, the 30th march, 1933.'' and its enabling formula (moved by the reviewed reading into block 141555)',
       '''(1) This notification may be cited as the North West Frontier Province Excise Powers and Appeal Orders. It shall come into force atonce.'' (block 141555); paragraphs 4-8 on page 8 (blocks 141556-141557)',
       'owner decision 2026-10-08 q1: paragraph 3.19 introduces a separate instrument'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1973-p7.png',
     '7dcd818dc436cd93bb5cc1dc26a18f27dfa8494be86b7c70df4a27c356520e47'),
    (141558::bigint,8,
     'West Pakistan notification under section 10 of the Punjab Excise Act appointing the Divisional Excise and Taxation Officers to be Collectors (superseding notification No. E&T-26/9-56 of 9 April 1956)',
     'notification',NULL::integer,NULL::text,
     jsonb_build_array(
       'page 8 prints, after NWFP paragraph 8, an unnumbered paragraph ''In exercise of the powers conferred by section 10 of the Punjab Excise Act (1 of 1914) ... in supersession of the West Pakistan Government notification No. E&T-26/9-56, dated the 9th April, 1956, the Governor of West Pakistan is pleased to appoint ...'' (block 141558); no caption, number or date of its own',
       'owner decisions: q1 a separate notification; export i q3 ''undated'' (no year), q4 ''number-1'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1973-p8.png',
     'ac311541e063d64d2c1f8aee419da0061106f8945176fbce42b49bfc3895d3ed'),
    (141559::bigint,8,
     'West Pakistan notification under section 5 of the Opium Act, 1878 appointing the Divisional Excise and Taxation Officers to be Collectors',
     'notification',NULL::integer,NULL::text,
     jsonb_build_array(
       'page 8 prints the next unnumbered paragraph ''In exercise of the power conferred by section 5 of the Opium Act 1878 read with rule 2 (g) of the Rules published with Revenue Department notification No. E&T 2/7-56 dated the 23rd November 1956 ...'' (block 141559); no caption, number or date of its own',
       'owner decisions: q1 a separate notification; export i q3 ''undated'', q4 ''number-1'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1973-p8.png',
     'ac311541e063d64d2c1f8aee419da0061106f8945176fbce42b49bfc3895d3ed'),
    (141560::bigint,8,
     'West Pakistan notification under section 8(2) of the Dangerous Drugs Act, 1930 appointing the Divisional Excise and Taxation Officers to be Collectors',
     'notification',NULL::integer,NULL::text,
     jsonb_build_array(
       'page 8 prints the third unnumbered paragraph ''In exercise of the powers conferred by sub-section (2) of section 8 of the Dangerous Drugs Act 1930 read with rule 2 (c) of the rules published under ... Notification No. Ex V/1/1-58, dated the 21st March, 1959 and in'' (block 141560), continued on page 9 (block 141561); no caption, number or date of its own',
       'owner decisions: q1 a separate notification; export i q3 ''undated'', q4 ''number-1'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc1973-p8.png',
     'ac311541e063d64d2c1f8aee419da0061106f8945176fbce42b49bfc3895d3ed')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,2341,1973,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-1973.json',
         'owner_decision',jsonb_build_array('.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
                                            '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json'),
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4,5,6,7,8,9,10,11),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 141494 THEN 'Block 141494 holds the Excise and Taxation Department notification No.52-75/26-EX (P)I of 7 January 1975 appointing the Director General Excise and Taxation as Excise Commissioner -- a separate instrument, not a preface to the Punjab Excise Powers and Appeal Orders (owner decision 2026-10-08, q1).'
         WHEN 141555 THEN 'Block 141555 begins the North West Frontier Province Government Revenue Department notification of 30 March 1933, the North West Frontier Province Excise Powers and Appeal Orders -- a separate instrument introduced by paragraph 3.19, not a continuation of the Punjab Orders (owner decision 2026-10-08, q1).'
         ELSE 'Block ' || c.start_block_id || ' begins one of the three undated West Pakistan notifications appointing Divisional Excise and Taxation Officers to be Collectors -- each a separate notification (owner decisions 2026-10-08 q1; 2026-10-10 q3 undated, q4 number-1).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-1973.json',
                          'owner_decision',jsonb_build_array(
                            '.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
                            '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json')),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=1973 AND c.source_observation_id=2341
   AND c.start_block_id IN (141494,141555,141558,141559,141560)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
