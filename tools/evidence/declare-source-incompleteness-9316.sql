--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9316, The Central Provinces Municipal Act, 1903 (Act XVI of 1903).
-- Observation 10538, https://drs.molaw.gov.pk/pdf/XVI-%20The%20Central%20Provinces%20Municipal%20Act%2C%201903.pdf, SHA-256 32cb8da8c26e001f42a7e4a98be3a9698a1a525f28dcc78356dee0afc17b7661.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9316, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10538 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10538 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10538 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10538, 9316, 'no_complete_copy_acquired', NULL,
       'Scan page 35 (printed Gazette page 137) ends inside section 170(2) ''The proceeds of any tax levied in any notified area under this section shall be expended only in some manner in which the municipal fund of such notified area might be expended if the notified area were a municipality.'' -- the file ends there.',
       'The contents promise sections 171 (Application of Act to notified areas), 172 (Effect of cancellation of notification issued under section 169) and 173 (Repeals), and the text that follows section 170.',
       'The owner read all 35 scans (8 are duplicates of earlier scans); the last scan, read again by the lead on its render, closes the right column with section 170(2) and prints nothing after it. A dated refetch of the official URL (acquisition_attempt 219, 7 November 2026) returned the identical 66,407,138-byte PDF. Sections 1-170 are all present; 171-173 are not printed in this copy.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 32cb8da8...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '32cb8da8c26e001f42a7e4a98be3a9698a1a525f28dcc78356dee0afc17b7661',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9316-p34.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9316-p35.png'),
         'render_sha256', jsonb_build_array('daae2493ca0c720e5835e50831e2e1c1487809170424e333d556aa7b382008c8', 'de71966e1f7f3567bf9b7bdb59b61ebae7659d0d66c601cb95ac11ad5faf74f4'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Sections 171, 172 and 173 and any text after section 170(2): not printed in the landed copy, which ends mid-Act.', 'last_printed_block_id', 2467083, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9316, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire a complete copy of the Central Provinces Municipal Act, 1903 (the Law Ministry portal copy drs.molaw.gov.pk stops at the foot of section 170); read it before adding sections 171-173. Preserve this source and declaration; no external wording used in this release.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10538
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10538);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10538) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10538: run tools/record_source_refetch.py --observation 10538 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10538;
