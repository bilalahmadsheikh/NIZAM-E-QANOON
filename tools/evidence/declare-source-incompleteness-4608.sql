--
-- DRAFT by agent JE (13 Oct 2026, prepare mode; not run). Pattern: declare-source-incompleteness-510.sql / -2205.sql.
--
-- Document 4608, The Sindh Local Government (Amendment) Act, 2014 (Sindh Act No. XVI of 2014).
-- Observation 3514, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000086.pdf, four PDF pages with
-- damaged page objects (MuPDF: 'non-page object in page tree', 'object is not a stream', content-stream syntax errors).
--
-- Owner decisions: decision-review-2026-10-12-j.json 4608 q1 'repair-from-image'; decision-review-2026-10-12-k.json
-- 4608 q2 'repair-and-gap' -- repair ss.1-8 as far as the text layer prints (joined spacing, doubled letters restored
-- only where certain, every change listed: claude/agJE/changes-4608.json), and release with a recorded source gap
-- after '... consist of a whole' in the inserted s.31-A(3).
--
-- Read (agent JE): p1 (507753370bff...) renders with broken glyphs; p2 (82975bcd...) the same; p3 (79125cda...)
-- renders solid black, its text layer printing s.18-A(5)(a)-(c), s.8 and the inserted s.31-A (1)-(3) to '... a ward
-- shall, as far as possible, consist of a whole' (block 963837), then only one-letter fragments; p4 (d87d0ed4...) is
-- blank with no text layer. No other copy of the Act is in the corpus.
--
-- ORDER: 1. python tools/record_source_refetch.py --observation 3514 --apply (a different valid PDF -> read it first);
--        2. this file. No contents reading follows (the Act prints no contents).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 3514 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 3514 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 3514, 4608, 'no_complete_copy_acquired', NULL,
       'Page 3, inserted section 31-A(3): the text layer ends "... a ward shall, as far as possible, consist of a whole"; '
       'page 3 renders black and page 4 is blank with no text layer.',
       'The rest of the inserted section 31-A(3) and anything the Act prints after it (any later sections, the '
       'authentication).',
       'All four pages read. ss.1-8 are released from the repaired text layer (spacing joined; 46 doubled letters '
       'restored where the word is certain, each listed for the owner); nothing after the cut is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same damaged four-page PDF; no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc4608-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4608-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4608-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4608-p4.png'),
         'render_sha256', jsonb_build_array(
           '507753370bfff44c9f5287c140ca20f16dfe09b995bcdf4754a8cd988db63f94',
           '82975bcd7ccadf3b0267658e238d24fdcee0e63bcbff3b5c4cd5e149cc11186b',
           '79125cda0f407a7d422b8a63b77985616febedd73089b6b96e36dd62bb9edd5c',
           'd87d0ed4a2881dcd8fef1fb6245340c31b42b4bc5892995a7f4f74639dac75ac'),
         'missing', jsonb_build_array(jsonb_build_object(
           'what', 'the rest of s.31-A(3) inserted by s.8, and anything after it', 'last_printed_block_id', 963837,
           'set_aside_fragment_blocks', jsonb_build_array(963835, 963838, 963839, 963840))),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-k.json',
           'document_id', 4608, 'question_id', 'q2', 'choice', 'repair-and-gap', 'reviewer', 'Bilal Ahmad'),
         'recovery_path', 'find the Sindh Government Gazette print of Sindh Act No. XVI of 2014 (28 October 2014) and '
                          'recover_acquisition.py --alternate-for 3514 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 3514
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 3514);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 3514) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 3514: run tools/record_source_refetch.py --observation 3514 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 3514;
