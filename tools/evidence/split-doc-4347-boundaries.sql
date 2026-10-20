-- Drafted by agent DF (12 Oct 2026, prepare mode); renamed without the -DRAFT suffix and applied by builder BZ
-- on 12 Oct 2026, with the plan tools/evidence/multi-instrument-plans/doc-4347.json. Status: (1) the 4347 decimal-numbering correction (claude/agDF/patch-4347.json) is
-- recorded and replayed (12 Oct 01:01); (2) the owner answered in chat, 12 Oct
-- (.artifacts/decision-review/exports/decision-review-2026-10-12-chat.json): 4347 q1 'undated' (the Purchase
-- Procedure), q2 '8.2-by-sequence' (rule 8's second '8.1', p34), and 'these must be released'. Still before
-- applying: (3) the materializer admits a per-expression 'jurisdiction' (E3 punjab; $S/agDF-matport.py) and the
-- plan tools/evidence/multi-instrument-plans/doc-4347-DRAFT.json is renamed doc-4347.json; (4) the agDF rule keys
-- are ported ($S/agDF-rule.py, $S/agDF-rule-hp.py) and the readings recorded: claude/agDF/patch-4347-split.json
-- (76), patch-4347-split-e6.json (12), patch-4347-split-optional-19.json (1, the p70 reading),
-- patch-4347-split-8.2.json (1).
--
-- Source-verified boundary evidence for the reviewed split of Sindh document 4347 (observation 4378, catalogued
-- as 'ssc rules & Regulation'). The official PDF is a booklet ('SINDH SEED CORPORATION RULES & REGULATIONS', p1)
-- printing seven instruments: the Service Regulations of the Sindh Seed Corporation, 1976 (pp1-29, regulations
-- 1-31); the Sindh Seed Corporation Recruitment Rules, 1976 (title page p30, rules 1-13 pp31-34, Annexures A-B
-- pp35-36, Appendix A pp37-44); the SSC Board's Delegation of Administrative and Financial Powers to the Managing
-- Director, 04.04.1978 (pp45-46); the Government of the Punjab notification No. S.O. (A-II)/8-47/75 of 18 January
-- 1977 that the Board attached (pp47-48); the Corporation's Purchase Procedure (undated, pp49-55); the Sindh Seed
-- Corporation Employees Leave Rules, 1980 ('Annexure-12', pp56-60); and the Provident Fund deed of trust (1 July
-- 1981) with the Provident Fund Rules, 1979 (pp61-77). Owner, 12 Oct 2026 (CLAUDE-CLAIMS.md): split.
-- The Regulations open the document at block 693438, so they need no boundary row.

\set ON_ERROR_STOP on
BEGIN;

WITH active_instrument AS (
  SELECT i.id
    FROM instrument i
   WHERE i.document_id=4347 AND i.source_observation_id=4378
     AND i.is_active AND i.duplicate_of IS NULL
), proposed(start_block_id,source_page,detected_title,detected_kind,detected_year,
            detected_number,source_facts,render_artifact,render_sha256) AS (
  VALUES
    (693816::bigint,30,
     'Sindh Seed Corporation Recruitment Rules, 1976',
     'rules',1976,NULL::text,
     jsonb_build_array(
       'page 29 ends the Service Regulations with 31.9 ''No Demand Certificate'' and prints nothing after it',
       'page 30 is a title page printing only the page number and ''REQUIREMENT RULES OF SINDH SEED CORPORATION''',
       'page 31 prints ''RECRUITMENT RULES / NOTIFICATION'' and ''In exercise of the powers conferred by Section 21 of the Sindh Seed Corporation Act XXIX. 1976, Government of Sindh ... is pleased to make the following Sindh Seed Corporation Recruitment Rules'', then rule 1.1 naming the ''Sindh Seed Corporation Recruitment Rules 1976''; rules 3 and 6.1 cite Appendix ''A'' (pp37-44), rules 10.1 and 11.1 cite Annexures ''A'' and ''B'' (pp35-36)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p30.png',
     '5916b97044545cf10136db47a26b396f8a5c737ced4dbd84eee08f531f7fee1f'),
    (694000::bigint,45,
     'Delegation of Administrative and Financial Powers to the Managing Director, Sindh Seed Corporation, 1978',
     'order',1978,NULL::text,   -- lead decision 12 Oct 2026: a Board decision -> kind order
     jsonb_build_array(
       'page 44 ends Appendix ''A'' of the Recruitment Rules (posts 45-60)',
       'page 45 prints ''THE DELEGATION OF ADMINISTRATIVE AND FINANCIAL POWERS TO THE MANAGING DIRECTOR, SINDH SEED CORPORATION, BY THE SSC BOARD IN ITS THIRD MEETING HELD ON 04.04.1978.'' and ''The Board ... approved ... on the pattern of Punjab Seed Corporation. (copy of Punjab Government Notification Attached).'', then groups 1-3 and items 1-22 (pp45-46)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p45.png',
     'fbaeaf9ff218733c3fb007b8cb84ee0f470f417616a86914b8372fe0587f61de'),
    (694025::bigint,47,
     'Government of the Punjab, Agriculture Department, Notification No. S.O. (A-II)/8-47/75, 1977 (delegation of powers to the Managing Director, Punjab Seed Corporation)',
     'notification',1977,NULL::text,
     jsonb_build_array(
       'page 47 prints ''GOVERNMENT OF THE PUNJAB, AGRICULTURE DEPARTMENT. NOTIFICATION. No. S.O. (A-II)/8-47/75- The Governor of the Punjab has been pleased to delegate ...'', groups I-II and items 1-17',
       'page 48 prints ''Dated Lahore, the 18th January, 1977. DR. MUHAMMAD NASEEM, Secretary to Government of the Punjab'' and the forwarding endorsement',
       'a Punjab instrument: the plan states jurisdiction punjab for this expression (lead decision 12 Oct 2026; the materializer gains a per-expression jurisdiction field)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p47.png',
     '8f4cf8a1687701e91a5bb6264854a1c4371597c3b99b3607e248b0a1d322ff9a'),
    (694036::bigint,49,
     'Sindh Seed Corporation Purchase Procedure',
     'order',NULL::int,NULL::text,
     jsonb_build_array(
       'page 49 prints ''SINDH SEED CORPORATION HYDERABAD / PURCHASE PROCEDURE.'' and paragraphs 1-2; paragraphs 3-7 follow to page 55; no date, number or authority is printed: owner decision 4347 q1 ''undated'' (decision-review-2026-10-12-chat.json; migration 0063 -- detected_year NULL)'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p49.png',
     '4f6bcdbe2142183d2b2a20e310f48c1f1c5d2dc42d2ff31c58a3e14f6364de92'),
    (694068::bigint,56,
     'Sindh Seed Corporation Employees Leave Rules, 1980',
     'rules',1980,NULL::text,
     jsonb_build_array(
       'page 55 ends the Purchase Procedure with paragraph 7 (stationery) v.',
       'page 56 prints ''Annexure-12 / SINDH SEED CORPORATION EMPLOYEES LEAVE RULES.'' and rule 1 ''These Rules shall be called as " Sindh Seed Corporation Employees Leave Rules 1980"''; rules 1-26 run to page 60'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p56.png',
     'f1a2ebd47020e884543f7f9c7721a6b86ef7653e0e1760a9057be2713c428b08'),
    (694128::bigint,61,
     'Sindh Seed Corporation Employees Provident Fund Rules, 1979',
     'rules',1979,NULL::text,
     jsonb_build_array(
       'page 60 ends the Leave Rules with rule 26',
       'page 61 prints ''SINDH SEED CORPORATION EMPLOYEES PROVIDENT FUND. DEED OF TRUST'' -- ''This INDENTURE MADE the 1st day of July-1981 ...'', ''WHEREAS the Corporation has determined to institute a Provident Fund ...'' and ''... according to the rules attached here to''; the seal and signatures (p63), ''EMPLOYEES PROVIDENT FUND RULES'' and rule 1 ''These Rules may be called provident Fund Rules, 1979.'' (p64), rules to p75, the First Schedule forms pp76-77'),
     '.artifacts/release-work-2026-09-24/claude/renders/doc4347-p61.png',
     '86771af8c75a4d3a42e11fced525695945e66ae066f07acd6318105b8b78fb11')
)
INSERT INTO segmentation_boundary_candidate (
    instrument_id,source_observation_id,document_id,start_block_id,source_page,
    detected_title,detected_kind,detected_year,detected_number,confidence,
    method,evidence
)
SELECT a.id,4378,4347,p.start_block_id,p.source_page,
       p.detected_title,p.detected_kind,p.detected_year,p.detected_number,1.0,
       'claude.multi-expression-plan/1',
       jsonb_build_object(
         'reviewer_type','assistant',
         'plan','tools/evidence/multi-instrument-plans/doc-4347.json',
         'owner_decision','.artifacts/release-work-2026-09-24/CLAUDE-CLAIMS.md (OWNER 12 Oct: split 4347); .artifacts/decision-review/exports/decision-review-2026-10-12-chat.json (4347 q1 undated, q2 8.2-by-sequence; release)',
         'source_facts',p.source_facts,
         'reviewed_pages',(SELECT jsonb_agg(g) FROM generate_series(1,77) g),
         'render_artifact',p.render_artifact,
         'render_sha256',p.render_sha256)
  FROM active_instrument a CROSS JOIN proposed p
ON CONFLICT (instrument_id,start_block_id,method) DO NOTHING;

INSERT INTO segmentation_boundary_adjudication (
    candidate_id,resolution,review_basis,method,rationale,evidence,decided_by
)
SELECT c.id,'confirmed_split','source_verified','claude.multi-expression-plan/1',
       'Block ' || c.start_block_id || ' (p' || c.source_page || ') begins ' || c.detected_title ||
       ' -- a separate instrument the booklet prints after the one before it (owner decision 12 Oct 2026: split 4347).',
       jsonb_build_object('reviewer_type','assistant','source_start_block_id',c.start_block_id,
                          'plan','tools/evidence/multi-instrument-plans/doc-4347.json',
                          'owner_decision','.artifacts/release-work-2026-09-24/CLAUDE-CLAIMS.md (OWNER 12 Oct: split 4347); .artifacts/decision-review/exports/decision-review-2026-10-12-chat.json (4347 q1 undated, q2 8.2-by-sequence; release)'),
       'claude.multi-expression-plan/1'
  FROM segmentation_boundary_candidate c
 WHERE c.document_id=4347 AND c.source_observation_id=4378
   AND c.start_block_id IN (693816,694000,694025,694036,694068,694128)
   AND c.method='claude.multi-expression-plan/1'
   AND NOT EXISTS (
       SELECT 1 FROM segmentation_boundary_adjudication a
        WHERE a.candidate_id=c.id AND a.resolution='confirmed_split');

COMMIT;
