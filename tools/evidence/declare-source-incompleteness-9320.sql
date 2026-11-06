--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9320, The Indian Merchant Shipping Act,1923.
-- Observation 10488, https://drs.molaw.gov.pk/pdf/XXI%20The%20Indian%20Merchnat%20Shipping%20Act%2C%201923.pdf, SHA-256 a7d72cc711cada7daeb7df69d835dcd2213253240cf71e86ae7e29f4b8ac80c7.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9320, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10488 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10488 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10488 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10488, 9320, 'no_complete_copy_acquired', NULL,
       'All296bodysections andfiveSchedulespresent on56pages; specificwordsfadedwithin116(1)(b)(ii), andtwoTOClabelsdamaged.',
       'Complete legible contents labels and words of116(1)(b)(ii).',
       'All56originalimagesread;6/25enlarged260/240dpi. Contents6shows[illegible]4.and2[illegible]5.only;25showslostwordsafterhe,afterscaleof,andbeforeseamen. Datedofficialrefetch216returnedidentical115286317-bytePDF; nosuperiorcopyacquired. Nothingreconstructedfromexpectedlaw.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 a7d72cc7...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'a7d72cc711cada7daeb7df69d835dcd2213253240cf71e86ae7e29f4b8ac80c7',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9320-p6.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9320-p25.png'),
         'render_sha256', jsonb_build_array('563c9d9904844a5f581800657f343ee2b4b14f9d96998b88c52f02bf733b3e60', '812b6684663675b8ae8ce23f6c429de8f865fb1d678247765d096834e7233256'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Two numeric contents-label fragments on page6; retain literal readable4.and2...5.with[illegible], no inferred full labels.', 'last_printed_block_id', NULL, 'resumes_block_id', NULL), jsonb_build_object('what', 'Three word gaps in section116(1)(b)(ii) page25: afterhe,afterscaleof,beforeseamen; retain[illegible].', 'last_printed_block_id', NULL, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9320, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Retain official acquisition216 unchanged_copy; obtain a better official scan if lateravailable, reread these exactpages, appendcurationandretirelimitationwithreviewedevidence. Noexternalstatutetextsupplied.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10488
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10488);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10488) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10488: run tools/record_source_refetch.py --observation 10488 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10488;
