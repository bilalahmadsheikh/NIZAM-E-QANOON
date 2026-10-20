-- Drafted by agent JE (12 Oct 2026, prepare mode). APPLIED once by builder BZ on 13 Oct 2026 (2 candidates + 2 confirmed_split
-- adjudications on the unreleased expression-11 instrument; append-only, idempotent on re-run), then renamed back to
-- -DRAFT with the plan while 4434 is PAUSED pending the owner (lead 13 Oct: the e3/e10/e20/e39 boundary corrections;
-- CLAUDE-CLAIMS). Source-verified boundary evidence for splitting document 4434 expression 11
-- (tools/evidence/multi-instrument-plans/doc-4434-DRAFT.json).
--
-- Expression 11 ('The Constitution (Thirteenth Amendment) Act, 1997', blocks 793249..793305, pp247-251) holds three
-- Acts. The page images (claude/renders/doc4434-p247..p251.png) print:
--   p247 (c85ee928...): 'The Constitution (Thirteenth Amendment) Act, 1997 (I of 1997) [4 April 1997]', ss.1-5;
--   p248 (6c4633cf...): 'The Constitution (Fourteenth Amendment) Act, 1997 (XXIV of 1997) [4 July 1997]' (block
--        793264), its preamble, s.1, s.2 inserting Article 63A (quoted, continued on p249, 879c3a5e...);
--   p250 (afbc68fd...): 'The Constitution (Sixteenth Amendment) Act, 1999 (VII of 1999) [5 August 1999]' (block
--        793294), its preamble, ss.1-2;
--   p251 (bb7df14a...): the Seventeenth Amendment Act (already expression 12).
-- Owner decision: decision-review-2026-10-12-j.json, document 4434, q2 'split' -- the Thirteenth Amendment ends before
-- p248's title; the Fourteenth Amendment Act, 1997 becomes its own expression. The Sixteenth Amendment Act on p250 was
-- not seen by the card; it is split on the same principle (lead to confirm; without it the Fourteenth's expression
-- would hold the Sixteenth's ss.1-2 and collide again).
--
-- The candidates are keyed to the active expression-11 instrument, whose tree spans both boundaries. Materialisation
-- is the separate, dry-run-gated `tools/materialize_multi_instrument.py --document 4434` from the reviewed plan, after
-- 4434 is moved from PRIMARY_DOCUMENTS to the plan route (in-memory build: the 40 released expressions rebuild SAME;
-- e11 S7 4 -> 0, 25 -> 7 nodes; new e43 16 nodes S7 0; new e44 4 nodes S7 0 -- claude/agJE/check-4434-plan.json).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id, i.source_observation_id
    FROM instrument i
   WHERE i.document_id=4434 AND i.expression_ordinal=11
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (793264::bigint,248,'The Constitution (Fourteenth Amendment) Act, 1997','act',1997,'XXIV',
     jsonb_build_array(
       'page 248 prints the title of a separate Act, (XXIV of 1997), dated [4 July 1997], with its own long title, preamble and enacting formula',
       'its s.1 names it the Constitution (Fourteenth Amendment) Act, 1997; s.2 inserts Article 63A (quoted, to p249)',
       'page 247 before it ends the Thirteenth Amendment Act at s.5 and its assent footnote'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4434-p248.png',
     '6c4633cf1e3cfa8d5fa9a15538c658085ae262a2372cb81b56a623bd3a44911a'),
    (793294::bigint,250,'The Constitution (Sixteenth Amendment) Act, 1999','act',1999,'VII',
     jsonb_build_array(
       'page 250 prints the title of a separate Act, (VII of 1999), dated [5 August 1999], with its own long title, preamble and enacting formula',
       'its s.1 names it the Constitution (Sixteenth Amendment) Act, 1999; s.2 amends Article 27',
       'page 249 before it ends the Fourteenth Amendment Act with the quoted Article 63A(6)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4434-p250.png',
     'afbc68fd98c5ee307c212959213203c9db0bd62027f16652214878778a7eb080')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,a.source_observation_id,4434,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4434.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'question_id','q2',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(247,248,249,250,251),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       CASE c.start_block_id
         WHEN 793264 THEN 'Block 793264 begins the Constitution (Fourteenth Amendment) Act, 1997 (XXIV of 1997), a separate Act printed after the Thirteenth Amendment Act (owner decision 2026-10-12 export j q2).'
         ELSE 'Block 793294 begins the Constitution (Sixteenth Amendment) Act, 1999 (VII of 1999), a separate Act printed after the Fourteenth Amendment Act (same principle as export j q2; lead confirmation).'
       END,
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4434.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=4434
   AND c.start_block_id IN (793264,793294)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
