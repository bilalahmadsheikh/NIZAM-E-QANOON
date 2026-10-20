-- Drafted by agent JC (12 Oct 2026); renamed and applied by builder BZ on 13 Oct 2026. Source-verified boundary evidence
-- for the reviewed split of document 3464 (tools/evidence/multi-instrument-plans/doc-3464.json).
--
-- The official PDF (observation 521, 'Pakistan Rangers Ordinance, 1959', Pakistan Code copy, 15 pages) prints the
-- Ordinance's contents on pp1-2, then on p3 a separate instrument -- '[This order may be read as an integral part of
-- The Pakistan Rangers Ordinance, 1959 (W.P. Ordinance XIV of 1959).]', 'THE WEST PAKISTAN RANGERS (ADMINISTRATION AND
-- CONTROL) ORDER, 1972 / PRESIDENT'S ORDER No. 19 OF 1972 / [20th April, 1972]', Articles 1-2 -- and the Ordinance's
-- text from p4 to p15.  The owner decided (decision-review-2026-10-12-j.json, doc 3464 q1 'split') that the Ordinance
-- is this document's instrument and P.O. No. 19 of 1972 a separate instrument linked to it by its printed note.
-- The Ordinance opens the document at block 385460 (its contents), so it needs no boundary row; the plan gives it two
-- spans (385460-385490 and 385500-385680) around the Order's span 385491-385499.
--
-- Materialisation is the separate, dry-run-gated `tools/materialize_multi_instrument.py --document 3464` run while the
-- single-tree instrument is still active, with the readings claude/agJC/patch-3464.json recorded first (4: E0 body
-- start p4 and three footnote blocks pp4, 10, 13).  Report-mode build ($S/agJD-mat.py): E0 126 provisions, S7 0,
-- contents 25/25 linked; E1 6 provisions (Articles 1-2), S7 0.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=3464 AND i.source_observation_id=521
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (385491::bigint,3,
     'The West Pakistan Rangers (Administration and Control) Order, 1972 (President''s Order No. 19 of 1972)',
     'order',1972,'President''s Order No. 19 of 1972',
     jsonb_build_array(
       'page 2 ends the Ordinance''s contents with FIRST SCHEDULE / SECOND SCHEDULE and the footer ''Page 2 of 15''',
       'page 3 opens with the note ''[This order may be read as an integral part of The Pakistan Rangers Ordinance, 1959 (W.P. Ordinance XIV of 1959).]'' (block 385491), then the title THE WEST PAKISTAN RANGERS (ADMINISTRATION AND CONTROL) ORDER, 1972, PRESIDENT''S ORDER No. 19 OF 1972, [20th April, 1972] and the enacting formula of the President and Chief Martial Law Administrator',
       'Articles 1 (Short title and commencement, (1)-(2)) and 2 (Vesting of superintendence ... in the Federal Government, (a)-(b)), footnote 1 ''Subs by F.A.O. 1975 ...''; page 4 opens the Ordinance''s own title ''1THE 2[PAKISTAN RANGERS] ORDINANCE, 1959'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3464-p3.png',
     'b746fde06e8ec32b359204c58fe557fa481d1dda919548584a839d43e0ccb72a')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,521,3464,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3464.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,2,3,4),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block 385491 begins the West Pakistan Rangers (Administration and Control) Order, 1972 (P.O. No. 19 of 1972) -- a separate instrument bound between the Ordinance''s contents and its text, linked to the Ordinance by its printed note (owner decision 2026-10-12, export j q1 split).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3464.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3464 AND c.source_observation_id=521
   AND c.start_block_id=385491
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
