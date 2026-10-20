--
-- DRAFT by agent JE (12 Oct 2026, prepare mode; not run). Pattern: declare-source-incompleteness-510.sql / -2211.sql.
--
-- Document 4565, catalogued 'INSTITUTE OF OPHTHALMOLOGY AND VISUAL SCIENCES EMPLOYEES (STUDENTS DISCIPLINE, CONDUCT,
-- WELFARE AND CODE OF HONOR) RULES, 2021'; the copy prints the Sindh Institute of Ophthalmology and Visual Sciences
-- (Students Discipline, Conduct, Welfare and Code of Honor) Regulations, 2021 (notification No. 3391/SIOVS/(Reg.)2021,
-- Hyderabad, 20 September 2021; Sindh Govt. Gazette Ext., 27 September 2021, gazette pages 1086-1089) and stops
-- mid-sentence at the foot of gazette page 1089.
--
-- Observation 4721, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000035.pdf,
-- SHA-256 73d07bd63247a2f9f281335a4867ad3c246ebadfb16a6a5417344889288c3bed, twelve pages.
--
-- Owner decisions: decision-review-2026-10-12-j.json, document 4565 (reviewer Bilal Ahmad):
--   q1 'main-only' -- the document carries only the Regulations (pp1-4); pp5-12 (gazette pages 1069-1076 of the IOVS
--      Employees Pay Scales Rules 2021, document 4575) are set aside, kept in the source, not citable;
--   q2 'release-with-gap' -- regulations 1-11 are released as far as printed; everything after '... involving moral
--      turpitude or' (gazette page 1090 onward) is recorded as source incompleteness (migration 0054).
--
-- Read from the renders on 2026-10-12 (agent JE): p1 (28ad88d3...) masthead, notification, regulations 1, 2, 3(1)(a)-(h);
-- p2 (1a0872bb..., gazette 1087) 3(1)(i), 3(2), 4 (i)-(x), 5 (i)-(xii); p3 (b97a6bb9..., 1088) 5 (xiii)-(xviii), 6, 7,
-- 8(1)-(2)(v); p4 (a54b2190..., 1089) 8(2)(vi), 8(3), 9 with its proviso, 10, 11 (1), (2), 'A. Conditions for Allotment
-- of accommodation in the Hostel.' (i)-(vi), 'B. Conditions of Ineligibility.' (i), (ii), and (iii) breaking off
-- '... for criminal offences(s) involving moral turpitude or' at the foot of the page. p5 (3a2cdc64..., gazette page
-- 1069) opens mid-rule 4 '(viii)' of the Pay Scales Rules; pp6-12 (076ff5be..., 8795dc3b..., 3537d9b5..., c7eb6ef0...,
-- 5c50c0ee..., 4cf3ab9c..., dfc21aa6...) are gazette pages 1070-1076 of those Rules, ending with rule 39 and
-- 'EXECUTIVE DIRECTOR'. No other text of the Regulations is in the corpus (owner card: corpus search found none).
--
-- Prepared tree (claude/agJE/patch-4565.json, 21 readings; pin claude/agJE/pin-4565.json): regulations 1-11 as printed;
-- regulation 11(2) ends with B (iii) cut at 'involving moral turpitude or'.
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 4721 --apply
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: the copy prints no contents list.
--
-- Idempotent: a second run inserts nothing once a record stands for 4721.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4721 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4721 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4721, 4565, 'no_complete_copy_acquired', NULL,
       'Page 4 (gazette page 1089) ends inside regulation 11, B. Conditions of Ineligibility, item (iii): "... or for '
       'criminal offences(s) involving moral turpitude or". Page 5 is gazette page 1069 of a different instrument.',
       'The rest of regulation 11 B(iii), any further items and regulations of the 2021 Regulations, and their '
       'authentication (gazette page 1090 onward).',
       'All twelve rendered pages read. pp1-4 (gazette pages 1086-1089): the notification of 20 September 2021 and '
       'regulations 1-11 to the cut. pp5-12 (gazette pages 1069-1076): the Institute of Ophthalmology and Visual Sciences '
       'Employees Pay Scales Rules 2021 (document 4575), set aside at the owner''s direction. Released as printed; '
       'nothing after the cut is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same twelve-page PDF '
                 '(SHA-256 73d07bd6...); no copy printing gazette page 1090 onward was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy of the Regulations was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '73d07bd63247a2f9f281335a4867ad3c246ebadfb16a6a5417344889288c3bed',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc4565-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4565-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4565-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4565-p4.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4565-p5.png'),
         'render_sha256', jsonb_build_array(
           '28ad88d30f8a926cf44fa7fdb466f1e896dd57ac52f4f3b8531aa7ade6a64e8a',
           '1a0872bbd24a92e8faffc4837acbf22f5ec1625591ba97d6483d7f39311b5fbc',
           'b97a6bb9e4b003973ea8c659d5de6b878a5d86f3f2a43736da04dd588abc35a3',
           'a54b21903e95e93dff943eb11d7b373fedb9ec4ef55937403aa275bfc2d9d2e1',
           '3a2cdc64bad5a4a28b9aa8feff5e75ec6ca9caf0ed35b08d3b6ddfcaf1b72350'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'the rest of regulation 11 B(iii) and everything after it (gazette page 1090 onward)',
                              'last_printed_block_id', 934332)),
         'bound_other_instrument', jsonb_build_object(
           'pages', jsonb_build_array(5, 6, 7, 8, 9, 10, 11, 12),
           'what', 'gazette pages 1069-1076 of the Institute of Ophthalmology and Visual Sciences Employees Pay Scales '
                   'Rules 2021 (document 4575); p6 is gazette page 1070, which document 4575 lacks',
           'treatment', 'set aside (source_apparatus_blocks), kept in the source, not citable'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 4565, 'question_ids', jsonb_build_array('q1', 'q2'),
           'choices', jsonb_build_array('main-only', 'release-with-gap'), 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction: regulations 1-11 as printed; the text after the cut is not '
                         'reconstructed; pp5-12 are set aside.',
         'recovery_path', 'find the Sindh Govt. Gazette Ext. of 27 September 2021, gazette pages 1086-1090+ (notification '
                          'No. 3391/SIOVS/(Reg.)2021), then recover_acquisition.py --alternate-for 4721 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4721
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4721);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4721) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4721: run '
                        'tools/record_source_refetch.py --observation 4721 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 4721;
