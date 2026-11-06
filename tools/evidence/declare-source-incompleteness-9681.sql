--
-- By the lead (28 Oct 2026). Pattern: declare-source-incompleteness-4521.sql.
--
-- Document 9681 (OCR revision of 5704), The Sind Sales of Motor Spirit Taxation Act, 1939 (Sind Act No. XX of 1939).
-- Observation 9770, https://sindhlaws.gov.pk/setup/Publications/PUB-14-000154.pdf,
-- SHA-256 5c250957c5a151f8c30bdf6957c5196ca5a00e3e4c7ff81cb826afd8aebc0a14, six pages (printed pp.60-62, 64-66).
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9681, q1 'release-with-gap' (owner chat
-- delegation of 25 Oct 2026; precedent doc 4521 q3). Nothing is supplied from elsewhere.
--
-- Read from the renders (lead): p3 (aeaff1b6...) is printed page 62 and ends with s.13(c) '... where any such retail
-- dealer carries on business or keeps any stock of motor spirit.'; p4 (c96a1981...) is printed page 64 and opens with
-- the tail of a margin note '... in making confiscation.' (block 2620833, set aside) and then s.18(1). Printed page
-- 63 -- sections 14 to 17 and the start of s.18's margin note -- is not in this copy.
--
-- ORDER: 1. python tools/record_source_refetch.py --observation 9770 --apply (done 28 Oct 2026: attempt 206,
-- unchanged_copy); 2. this file. No contents reading follows (the Act prints no contents).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 9770 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 9770 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 9770, 9681, 'no_complete_copy_acquired', NULL,
       'PDF page 3 (printed page 62) ends with section 13(c) "... keeps any stock of motor spirit."; PDF page 4 is '
       'printed page 64 and opens with the end of a margin note ("in making confiscation.") and section 18(1).',
       'Printed page 63: sections 14, 15, 16 and 17, and the margin heading of section 18.',
       'All six rendered pages read. Sections 1-13 and 18-26 are printed in full (the Act prints no contents list; '
       'section 21(1)(i) and 26(2)(f) refer to "the officer empowered under section 14", and section 18(1) to '
       '"confiscation under section 17", which confirms the gap). Released under the owner''s delegation with the '
       'missing page recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same six-page PDF (SHA-256 5c250957...); '
                 'no copy printing page 63 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing page 63 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '5c250957c5a151f8c30bdf6957c5196ca5a00e3e4c7ff81cb826afd8aebc0a14',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc9681-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc9681-p4.png'),
         'render_sha256', jsonb_build_array(
           'aeaff1b6c87af1356fc64ba7957b50456de4cc30560c6aaf6d5a6ba13505b23b',
           'c96a1981176561daa398c626070c03ecd3b2defb21ac1639a44947de760caeb6'),
         'missing', jsonb_build_array(jsonb_build_object(
           'what', 'printed page 63: sections 14-17', 'set_aside_block_id', 2620833,
           'last_printed_block_id', 2620829, 'resumes_block_id', 2620834)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9681, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find another print of Sind Act No. XX of 1939 (the Sind Code volume, or the Sind Government '
                          'Gazette of July 1939) and recover_acquisition.py --alternate-for 9770 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 9770
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9770);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9770) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 9770: run tools/record_source_refetch.py --observation 9770 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 9770;
