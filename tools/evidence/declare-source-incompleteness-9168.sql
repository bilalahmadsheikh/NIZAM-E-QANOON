--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9168, The Inland Customs Act, 1875 (Act No. VIII of 1875).
-- Observation 13201, https://drs.molaw.gov.pk/pdf/VIII%20The%20Inland%20Customs%20Act%2C%201875.pdf, SHA-256 f92d29d6f83d0fc9348fd2f80e6a58e19ceeeeee8fe148433aeb49ea744ca5d4.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9168, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 13201 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 13201 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 13201 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 13201, 9168, 'no_complete_copy_acquired', NULL,
       'PDF page 5 (printed page 62) is the last page of the copy and ends with section 28: ''... prohibit absolutely, or subject to conditions, the [import, export or] transit of salt or of sugar into, out of, or over, the said territories or any part thereof.''',
       'Sections 29 to 33 (rules, publication of rules, powers of Local Government, saving of existing duties, existing rules and customs-line) and the schedule of repealed enactments, printed on the following page(s) of the Gazette of 6 March 1875.',
       'All five rendered pages read: printed pages 58 to 62, the contents (promising sections 1-33) and the body through section 28. No page after printed page 62 is in this copy. Released under the owner''s delegation with the missing pages recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 f92d29d6...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'f92d29d6f83d0fc9348fd2f80e6a58e19ceeeeee8fe148433aeb49ea744ca5d4',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9168-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9168-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9168-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9168-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9168-p5.png'),
         'render_sha256', jsonb_build_array('760fd1ac318ece985961eee691c7d3b37ee297029018f50892966ff4a14d3692', 'c16723ac6770346577c284e5cbc6cede299def78c4f4f697fddfdf636d5a958a', 'bf00bebc42f02d7f45aebeba6fa8243cbcc57ea95fb14e2ab80de4b379a1ed14', '6d645765f633c2de65b9ccc2788c07372d1fc59e8c357c8f6bd6b6ab16d6dd55', '03a9125235b938a3091fd02bad6942a0ff2b5d8d9860ce3cd898f99103ba6627'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'the page(s) after printed page 62: sections 29-33 and the schedule', 'last_printed_block_id', NULL, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9168, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find another print of Act No. VIII of 1875 (the Gazette of India of 6 March 1875, Part IV, or the Unrepealed General Acts) and recover_acquisition.py --alternate-for 13201 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 13201
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13201);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13201) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 13201: run tools/record_source_refetch.py --observation 13201 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 13201;
