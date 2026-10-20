--
-- DRAFT by agent JE (12 Oct 2026, prepare mode; not run). Pattern: declare-source-incompleteness-510.sql / -4565-DRAFT.sql.
--
-- Document 4521, The Regulation of Mines and Oilfields and Mineral Development (Government Control) (Amendment) Act,
-- 2022 (Balochistan Act No. XVI of 2022), notification of the Provincial Assembly Secretariat of 9 June 2022.
-- Observation 1280, http://balochistancode.gob.pk/lawdir/8ac05719-6075-4d8b-b7e2-b4c808e72026.pdf,
-- SHA-256 e4a42d2c871313c999921764596e00f49b7105eb8397049b9e75ce52c138d971, two pages.
--
-- Owner decision: decision-review-2026-10-12-j.json, document 4521, q3 'release-with-gap': the half-visible line is not
-- transcribed by guess; the inserted s.7(3)(a) is released with a recorded source gap ('one line cut off at the foot
-- of p1'); the diary mark is set aside.
--
-- Read from the renders (agent JE): p1 (37e9f10c...) ends '(a) the term "Negotiated Agreement" shall mean a commercial
-- agreement between one or more persons and the Provincial' and then only the top half of one more line
-- ('Government entered into through ...', block 927325, set aside); p2 (02f7f410...) resumes 'without public tendering,
-- regarding the grant of a license, lease or other rights ...'. The words of the cut line are not legible.
--
-- ORDER: 1. python tools/record_source_refetch.py --observation 1280 --apply (if it lands a DIFFERENT valid PDF, read
-- that copy first -- this file then refuses); 2. this file. No contents reading follows (the Act prints no contents).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 1280 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 1280 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 1280, 4521, 'no_complete_copy_acquired', NULL,
       'Page 1, inserted section 7(3)(a): after "... between one or more persons and the Provincial" the last line of the '
       'page is cut by the scan (only the tops of the letters of "Government entered into through ..." show); page 2 '
       'resumes "without public tendering, regarding the grant of a license ...".',
       'One printed line of the inserted section 7(3)(a), between "the Provincial" (p1) and "without public tendering" (p2).',
       'Both rendered pages read. The rest of the Act (title, preamble, s.1(1)-(3), s.2 with the quoted s.7 (1), (2), '
       '(3)(a)-(b) and proviso) is printed in full. Released at owner direction with the cut line recorded as missing; '
       'nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same two-page PDF (SHA-256 e4a42d2c...); '
                 'no copy printing the cut line was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the cut line was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'e4a42d2c871313c999921764596e00f49b7105eb8397049b9e75ce52c138d971',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc4521-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4521-p2.png'),
         'render_sha256', jsonb_build_array(
           '37e9f10c797ab41f8082fa96212c9ba38e83de72e3d9f1943817e87834f63ea7',
           '02f7f41004bf72c2aab105fedc08af3dda0f1ec83d74a0bd2f6bf31cdf12393c'),
         'missing', jsonb_build_array(jsonb_build_object(
           'what', 'one line of the inserted s.7(3)(a) at the foot of p1', 'set_aside_block_id', 927325,
           'last_printed_block_id', 927324, 'resumes_block_id', 927326)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 4521, 'question_id', 'q3', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'recovery_path', 'find the Balochistan Gazette print of Act No. XVI of 2022 (or the Assembly notification '
                          'No.PAB/Legis:V(20)/2022/8371) and recover_acquisition.py --alternate-for 1280 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 1280
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 1280);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 1280) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 1280: run tools/record_source_refetch.py --observation 1280 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 1280;
