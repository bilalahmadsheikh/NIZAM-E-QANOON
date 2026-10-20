-- Drafted by agent DD (11 Oct 2026, prepare mode); renamed without the draft suffix and applied by builder BZ
-- on 11 Oct 2026. Source-verified boundary evidence for the reviewed split of Sindh document 4428
-- (tools/evidence/multi-instrument-plans/doc-4428.json).
--
-- The official PDF (observation 3150, catalogued as the Sindh Public Procurement Act, 2009) prints two
-- instruments: pages 1-15 the Sindh Public Procurement Act, 2009 (Sindh Act No. IV of 2009: contents pp1-2,
-- sections 1-27 pp3-15) and pages 16-88 the Sindh Public Procurement Rules, 2010 (title page p16, contents
-- pp17-22, 'NOTIFICATION' and rules 1-91 with 15-A, 15-B, 21-A, 32-A, 82-A, 82-B, 85-A, 85-B pp23-88). The owner
-- decided on 11 Oct 2026 (CLAUDE-CLAIMS.md, OWNER ANSWERS): split, the Act and the Rules; the current single
-- tree stays released until the split is ready. The Act opens the document at block 783733, so it needs no
-- boundary row; the Rules open at the p16 title page, block 783926.
--
-- Precedents: split-doc-1839-boundaries.sql, split-doc-1626-boundaries.sql. This file appends evidence only;
-- materialisation is the separate, dry-run-gated
--   python tools/materialize_multi_instrument.py --document 4428
-- run (with --approve-release-change: the released Act instrument is replaced) while the single-tree instrument
-- is still active, after: (1) the plan is renamed doc-4428.json; (2) the 110 readings
-- ($S/agDD-readings-4428.json) are recorded; (3) PLAN_RELATIONS admits 'empowers' (docs/03b; the relation
-- runs from E0's s.26 to E1, lead decision 11 Oct).

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=4428 AND i.source_observation_id=3150
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (783926::bigint,16,
     'Sindh Public Procurement Rules, 2010',
     'rules',2010,NULL::text,
     jsonb_build_array(
       'page 15 ends the Act with s.27 ''The Authority may make regulations ... for carrying out the purposes of this Act.'' and the page number 15; the Act prints nothing after s.27',
       'page 16 is a title page printing only ''THE SINDH PUBLIC PROCUREMENT RULES, 2010'' and the page number 16',
       'pages 17-22 are the Rules'' own contents (Rule No. / Page No.), page 23 prints ''THE SINDH PUBLIC PROCUREMENT RULES, 2010'', ''NOTIFICATION'' and rule 1 ''(1) These rules shall be called the Sindh Public Procurement Rules, 2010.''; rule 2(1)(a) defines ''Act'' as the Sindh Public Procurement Act, 2009',
       'this copy prints no enabling formula, date or notification number for the Rules; their amendment notes cite SGA&CD Notification No SORI(SGA&CD) 2-30/2010'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4428-p16.png',
     'ea112919d3bf526c57c5b95b839625f7928b113987b257048e50ee25780ea19f')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,3150,4428,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4428.json',
         'owner_decision','.artifacts/release-work-2026-09-24/CLAUDE-CLAIMS.md (OWNER ANSWERS 11 Oct)',
         'source_facts',p.source_facts,
         'reviewed_pages',(SELECT jsonb_agg(g) FROM generate_series(1,88) g),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block 783926 (p16 title page) begins the Sindh Public Procurement Rules, 2010 -- a separate instrument made under s.26 of the Sindh Public Procurement Act, 2009 that the file prints after the Act (owner decision 11 Oct 2026: split).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4428.json',
                          'owner_decision','.artifacts/release-work-2026-09-24/CLAUDE-CLAIMS.md (OWNER ANSWERS 11 Oct)'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=4428 AND c.source_observation_id=3150
   AND c.start_block_id=783926
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
