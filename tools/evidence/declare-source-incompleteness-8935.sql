--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 8935, The High Court Judges (Travelling Allowances) Order, 1965 (President's Order No. 4 of 1965).
-- Observation 13064, https://drs.molaw.gov.pk/pdf/IV-%20The%20Judges%20%28Travelling%20%20Allowances%29%20Order%2C%201965.pdf, SHA-256 7c65672aca4dd400e0a78006bd5f1429d188e2022fbf512bc7872ab219321a91.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 8935, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 13064 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 13064 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 13064 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 13064, 8935, 'no_complete_copy_acquired', NULL,
       'PDF page 6 (printed page 134) is the last page of the copy and ends inside article 10(2)(d): ''... from the residence of the judge at the old station to his residence at the new station, irrespective of the mode by which the''.',
       'The rest of article 10(2)(d) and articles 11 to 16 (daily allowance, travel when not on duty, travel to join post, shortest route, repeal), printed on the following pages.',
       'All six rendered pages read: the contents (articles 1-16) and the body through article 10(2)(d), printed pages 129-134. No later page is in this copy. Handwritten amendment notes on pages 4 and 5 are set aside. Released under the owner''s delegation with the missing pages recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 7c65672a...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '7c65672aca4dd400e0a78006bd5f1429d188e2022fbf512bc7872ab219321a91',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc8935-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8935-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8935-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8935-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8935-p5.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8935-p6.png'),
         'render_sha256', jsonb_build_array('7a7f9b192352aa054cdc98d31f9719f0ab7055e343ada12332ef5d63efbd7570', '82e45dd3cc29aa8d32bf3e69c08d1774d0f257c6aeec3de9871cf3cf636eda5b', 'cbe8aaef5e15f25e0f12e1671a9155afd4636f400f475955fc7e258c0d9ca1d3', 'd767cd78e59a25b444affb2664e2efae536be2c89fd035524a3a3bc0e9b28308', 'a377b4aecb31ade2eae29e83b613c2877463b6db8353f161c5a249af7b1f2d83', 'c58dc352beb244622abba45733d66454b6c4dc71cec0843e2532f5548df09685'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'the pages after printed page 134: end of article 10 and articles 11-16', 'last_printed_block_id', NULL, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 8935, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find another print of President''s Order No. 4 of 1965 (Gazette of Pakistan, Extraordinary, 11 August 1965, or the Pakistan Code volume) and recover_acquisition.py --alternate-for <observation> --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 13064
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13064);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13064) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 13064: run tools/record_source_refetch.py --observation 13064 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 13064;
