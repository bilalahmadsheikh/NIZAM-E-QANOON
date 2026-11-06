--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 8962, The Chutia Nagpur Encumbered Estates Act, 1876 (Act No. VI of 1876).
-- Observation 10585, https://drs.molaw.gov.pk/pdf/VI%20The%20Chutia%20Nagpur%20Encumbered%20Estates%20Act%2C%201876.pdf, SHA-256 9392ee2c34ac0e4121a9d919675ea5f180949b59915428fb12b93cad57aaba9d.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 8962, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10585 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10585 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10585 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10585, 8962, 'no_complete_copy_acquired', NULL,
       'PDF page 1 is the gazette''s first page and prints only the contents (rows of sections 1-18); PDF page 2 is printed page 110 and opens with the last words of section 12 (''revived debts and liabilities, the time intervening ... shall be excluded.'').',
       'The rest of the contents (Part VI, sections 19-24), the preamble, sections 1 to 11, and section 12 save its last words.',
       'All three rendered pages read. The copy prints the first contents page, printed page 110 (end of section 12, sections 13-21) and printed page 111 (sections 22-24 and the signature). The pages between the contents page and page 110 are not in this copy, and no section 1-11 is printed anywhere in it. Released under the owner''s delegation with the missing pages recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 9392ee2c...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '9392ee2c34ac0e4121a9d919675ea5f180949b59915428fb12b93cad57aaba9d',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc8962-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8962-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc8962-p3.png'),
         'render_sha256', jsonb_build_array('84036640e2b271b7b2fa9008dce12d42f28a84088d7f64a7471b98af2e56bea2', 'a791fb045ad57ce853e771c95af01002a246b7fe13b41bc64de5411a32224609', 'aa1e014e2ffba60a81d279fb896350d080ee2deb1b026424256730aecff5e698'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'the pages between the contents page and printed page 110: preamble, sections 1-11 and most of section 12', 'last_printed_block_id', 2356882, 'resumes_block_id', 2356892)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 8962, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find another print of Act No. VI of 1876 (the Gazette of India of 1 April 1876, Part IV, or the Bengal Code / Unrepealed Central Acts) and recover_acquisition.py --alternate-for 10585 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10585
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10585);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10585) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10585: run tools/record_source_refetch.py --observation 10585 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10585;
