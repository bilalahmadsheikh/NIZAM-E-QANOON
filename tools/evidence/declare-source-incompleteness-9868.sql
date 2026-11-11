--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9868, Federal Excise Rules2005 - local Appeal Register heading clipping only.
-- Observation 10798, https://drs.molaw.gov.pk/pdf/ilovepdf_merged%20%2810%29_1.pdf, SHA-256 b259df7ddb12e74a8db45c2e989d2990f4fd3599bc7a1f17575f8b7bfa8c0ae0.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9868, q3
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10798 --apply (done 8 Nov 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10798 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10798 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10798, 9868, 'no_complete_copy_acquired', NULL,
       'Full compilation present through main rule89 and Annex-II p93; independent Electronic Filing rules1-5 endp96. Local loss only in p60 register status heading.',
       'Complete heading of the status column in the Appeal Register under rule48K',
       'Physical p60 rightmost register status cell cuts off the last glyph(s) after varied/altere; no closing parenthesis follows other. Retained as altere[illegible]; no expected ending or punctuation supplied. All substantive rules and96 pages were individually read.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 b259df7d...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'b259df7ddb12e74a8db45c2e989d2990f4fd3599bc7a1f17575f8b7bfa8c0ae0',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/codex-7064-2026-11-08/doc9868-p60.png'),
         'render_sha256', jsonb_build_array('61536fced74add8e5242eb1075dfc738ac9669cf5b15369dc844cfbcba781ba3'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Local clipped status-heading glyph(s) after altere in p60 register table; not a missing rule/page', 'last_printed_block_id', 2691269, 'resumes_block_id', 2691270)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9868, 'question_id', 'q3', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'OfficialURL refetched8Nov2026: acquisition_attempt224 HTTP200 unchanged_copy sameSHA. Revisit only if an actually more complete official copy is acquired; retainrawsource and this local limitation.'),
       'codex.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10798
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10798);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10798) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10798: run tools/record_source_refetch.py --observation 10798 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10798;
