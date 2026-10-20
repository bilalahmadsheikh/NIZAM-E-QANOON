-- adopted by builder BZ 16 Oct 2026 (renamed from -DRAFT; applied by the owner-run batch).
-- DRAFT by agent K4 (16 Oct 2026, prepare mode; the builder renames and applies it). Source-verified boundary evidence
-- for the realigned split of document 3696 (tools/evidence/multi-instrument-plans/doc-3696.json), on the owner's
-- decision-review-2026-10-12-j.json q1 'split' and the delegated answers decision-review-2026-10-15-delegated.json
-- q2 'split-and-realign' and q3 'keep-both'.
--
-- The gazette (observation 4624, 26 pages, Sindh Govt. Gazette Extraordinary of 22 September 1998) prints six
-- instruments: the Appointment, Promotion and Transfer Regulation 1997 (pp1-5), the Efficiency and Disciplinary
-- Regulation 1997 (pp6-13), the Probation, Confirmation and Seniority Regulation 1997 (pp13-16), the Pension Regulation
-- 1997 (pp17-18; gazette pages 312-313 -- the copy holds no gazette pages 306-311), the Group Insurance Regulations 1998
-- (pp19-25) and the Conduct Rules 1996 notification (p26). Released today from the legacy manifest: E0-E2, with E1 and E2
-- starting two blocks late and the Pension Regulation inside E2. A RELEASED CHANGE: every released path is accounted for
-- in claude/agK4/3696-path-moves.json (same 68, text 22 -- page heads removed --, moved 128, gone 5 = four false Parts
-- opened by page heads and the bogus section '1997 No' of E1; nothing of law drops out). The builder drops 3696 from
-- PRIMARY_DOCUMENTS in tools/materialize_multi_instrument.py when the plan is renamed.
--
-- Materialisation is the dry-run-gated `tools/materialize_multi_instrument.py --document 3696`, after the readings
-- claude/agK4/patch-3696.json are recorded (agent K4's prototype rules O `order_suffix_one_block_section` and Q
-- `reviewed_part_line` ported first). Report-mode build: E0 64, E1 86, E2 48, E3 21, E4 99, E5 5 provisions; S7 0.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=3696 AND i.source_observation_id=4624
     AND i.is_active AND i.duplicate_of IS NULL AND i.expression_ordinal=0
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (448227::bigint,6,'Sindh Poultry Vaccine Centre (Efficiency and Discipline) Regulations, 1997','regulation',1997,
     NULL::text,
     jsonb_build_array('page 5 ends regulation 18 of the Appointment, Promotion and Transfer Regulation 1997',
                       'page 6 opens with the gazette head ''295 THE SINDH GOVT. GAZETTE EXT, SEPTEMBER 22, 1998 PART-I'', then the title ''SINDH POULTRY VACCINE CENTRE (EFFICIENCY AND DISCIPLINARY) REGULATION 1997'' (blocks 448227-448229) and ''No. SO(AMDN)L&F/9-3/97: In exercise of powers ...'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3696-p6.png',
     '627a26edda063a7f5ce5964006542d0b26dc2913096921d0c0336c77a06b2442'),
    (448237::bigint,13,'Sindh Poultry Vaccine Centre Employees (Probation, Confirmation and Seniority) Regulation 1997',
     'regulation',1997,NULL::text,
     jsonb_build_array('page 13: regulation 14 of the Efficiency and Discipline Regulations ends the page head 302 block',
                       'then the title ''SINDH POULTRY VACCINE CENTRE (PROBATION, CONFIRMATION AND SENIORITY) REGULATION 1997'' (blocks 448237-448239), ''NO.SO(AMIN)LIW/93/97: In exercise of powers ...'', PART - I GENERAL'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3696-p13.png',
     'da4ada6801b7cb8c1b665d6853b289b482083d119f73f42a62da2efae7de6bcd'),
    (448251::bigint,17,'Sindu Poultry Vaccine Centre (Pension) Regulation 1997','regulation',1997,'SO(ADMN)L&F/9-3/9',
     jsonb_build_array('page 16 (gazette page 305) ends the Probation Regulation with its regulations 13-14 and signature',
                       'page 17 is gazette page 312: ''SINDU POULTRY VACCINE CENTRE (PENSION) REGULATION 1997 / Karachi dated the 6th December.1997 / No. SO(ADMN)L&F/9-3/9: In exercise of powers conferred by section 70 ...'', regulations 1-3; page 18 regulations 4-5; released today inside E2 as its second ''Part I'''),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3696-p17.png',
     '1587f5a967db1565cec5f3e78a7263ad29e20c71152ccb36ca5996d2cdae32a8'),
    (448258::bigint,19,'Sindh Poultry Vaccine Centre Group Insurance Regulations, 1998','regulation',1998,NULL::text,
     jsonb_build_array('page 19 opens with the gazette head 314, then ''SINDH POULTRY VACCINE CENTRE (GROUP INSURANCE) REGULATIONS 1998 / Karachi, dated: 27th May, 1998 / No. SO(ADMN)/L&F/9-3/97 ...''',
                       'regulations 1-17 (17 printed twice, owner q3 keep-both), SCHEDULE, Annexures A-C, signature (p25)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3696-p19.png',
     'ac7263f9ebe0926e2017b3ed1b4b89b020263faae1c5c2aae6e836bbfb53ae54'),
    (448278::bigint,26,'Sindu Poultry Vaccine Centre (Conduct) Rules, 1996','rules',1996,'SO(ADMN)/L&F/9-3/97',
     jsonb_build_array('page 26 opens with the gazette head 321, then ''SINDU POULTRY VACCINE CENTRE (CONDUCT) RULES, 1996. / Karachi, dated the 14th January, 1997. / NO: SO(ADMN)/L&F/9-3/97 ...'' and modifications (1)-(5); then the press line'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc3696-p26.png',
     '2b924a846e3895a84d7fca6bc7d738c53e43226bfb89eb81c04151c99f44a1e7')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,4624,3696,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-3696.json',
         'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
         'delegated_decision','.artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json',
         'source_facts',p.source_facts,
         'reviewed_pages',jsonb_build_array(1,5,6,13,16,17,18,19,25,26),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block '||c.start_block_id||' begins '||c.detected_title||' at its printed title (owner decision export j q1 split; delegated q2 split-and-realign).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-3696.json',
                          'owner_decision','.artifacts/decision-review/exports/decision-review-2026-10-15-delegated.json'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=3696 AND c.source_observation_id=4624
   AND c.start_block_id IN (448227,448237,448251,448258,448278)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
