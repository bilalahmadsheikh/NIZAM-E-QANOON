-- Source-verified boundary evidence for the reviewed split of Sindh document 2146
-- (tools/evidence/multi-instrument-plans/doc-2146.json).  Drafted by agent CQ (10 Oct 2026, prepare mode);
-- renamed without the draft suffix and applied by builder BZ on 10 Oct 2026.
--
-- The Budget Rules (expression 1) were verified page by page on 10 Oct (agent CQ) on the owner's answers of that day
-- (via the lead, logged in CLAUDE-CLAIMS.md): both instruments release together, and the Budget Rules' two source
-- gaps (no rule 4; Forms B-5 to B-20 absent, Form B-4 cut off at the end of the PDF) are recorded by
-- tools/evidence/declare-source-incompleteness-2146.sql.  Readings for both expressions:
-- claude/agCQ/patch-2146.json; the Budget Rules also need the prototype rule explanation_of_heading (agCQ-rule.py J).
--
-- The official PDF (observation 4503, catalogued as 'SINDH LOCAL COUNCILS (PROPERTY) RULES, 2017') prints two
-- independent instruments: pages 1-7 the Sindh Local Councils (Property) Rules, 2017 (notification
-- No.RO(LG)/MISC:/4(74)/2016 of 28 February 2017, rules 1-15, signature and (p6) forwarding, then (p7) the Schedule
-- '(see rule 5)' of registers (1)-(21)); pages 8-32 the Sindh Councils (Budget) Rules, 2017 (its own notification
-- No.RO(LG)/MISC:4(74)/2016 of 28 February 2017, rules 1-84, signature, (p25) forwarding, and Forms B-1 to B-4).
-- The owner decided this on 2026-10-10 (decision-review-2026-10-10-i.json, doc 2146 q1 'split', note: "Pages 1-7
-- shall constitute the Sindh Local Councils (Property) Rules, 2017, including their Schedule ... Pages 8-32 shall
-- constitute a separate instrument titled the Sindh Councils (Budget) Rules, 2017 ...").  The Property Rules open the
-- document at block 162547, so they need no boundary row; the Budget Rules (block 162665, p8) do.
-- Doc 268 / 691 / 1822 precedent: tools/evidence/split-doc-268-boundaries.sql, split-doc-1822-boundaries.sql.
--
-- This file appends evidence only.  Materialisation is the separate, dry-run-gated
-- `tools/materialize_multi_instrument.py --document 2146`, run while the single-tree instrument is still active.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=2146 AND i.source_observation_id=4503
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (162665::bigint,8,
     'Sindh Councils (Budget) Rules, 2017',
     'rules',2017,NULL::text,
     jsonb_build_array(
       'page 7 ends the Property Rules'' Schedule with ''(21) Register of losses in Form P-XXI'' and the page number; page 8 opens with a new head GOVERNMENT OF SINDH / LOCAL GOVERNMENT AND HOUSING TOWN PLANNING / DEPARTMENT (blocks 162665-162666)',
       'its own date ''Karachi, dated the 28th February, 2017'' (block 162667), caption N O T I F I C A T I O N (block 162668) and enabling formula ''No.RO(LG)/MISC:4(74)/2016: In exercies of the power conferred by section 138 read with sub-section (6) of section 109 of the Sindh Local Government Act, 2013, and item No.14 of Schedule VII thereof ... following rules:-'' (block 162669)',
       'its own CHAPTER-I PRELIMINARY and rule 1 ''(1) These rules may be called the Sindh Councils (Budget) Rules, 2017.'' (blocks 162670-162673), rules 1-84 in five chapters, its own signature (p24) and forwarding (p25), and Forms B-1 to B-4 (pp26-32)',
       'it is a different instrument from the Property Rules: a different enabling provision (s.138 with s.109(6) and item 14 of Schedule VII, against s.138 with s.117 and entry 8), its own short title and its own rule numbering from 1; owner decision q1 ''split'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc2146-p8.png',
     'b6b356522a9d85c8fe90e4a57761ed75508ceae6adb031bb941c57da1d0a1a59')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,4503,2146,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-2146.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
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
       'Block 162665 begins the Sindh Councils (Budget) Rules, 2017 -- a separate instrument with its own notification of 28 February 2017, its own rules 1-84 and Forms B-1 to B-4, not part of the Sindh Local Councils (Property) Rules, 2017 printed before it (owner decision 2026-10-10, q1 split).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-2146.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-10-i.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=2146 AND c.source_observation_id=4503
   AND c.start_block_id IN (162665)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
