--
-- By Codex (7 Nov 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9852, NEPRA (Uniform System of Accounts) Regulations, 2022.
-- Observation 12543, https://drs.molaw.gov.pk/pdf/3.23%20-%20Copy.pdf, SHA-256 8a45c20939c8c29cf84402dd2df258dd7f5e7530d63e93f0bcf9b06e2b5384e1.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9852, q2
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 12543 --apply (done 7 Nov 2026, acquisition_attempt221); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 12543 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 12543 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 12543, 9852, 'no_complete_copy_acquired', NULL,
       'No missing pages; only the paragraph label immediately before the books of accounts on physical page3 is obscured by a registrar stamp.',
       'Preserve all visible regulation4(1) text; no fabricated clause label.',
       'Page3 registrar seal covers the separate paragraph label preceding the books of accounts shall be maintained as per the format provided in Schedule II to these regulations. The visible words are retained under regulation4(1) with [illegible] explicitly marking the lost label, not attributed to preceding clause(b), and no(c) citation is manufactured. Refetch221 returned the identical5,204,482-byte PDF.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 8a45c209...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '8a45c20939c8c29cf84402dd2df258dd7f5e7530d63e93f0bcf9b06e2b5384e1',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9852-p3.png'),
         'render_sha256', jsonb_build_array('e66da62622c3640281b33a66a4812931e214bcfb9ff0d745a45b718dea922c5b'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Only the seal-obscured clause-label locus before the books of accounts on physical page3; no missing-page or missing-body allegation.', 'last_printed_block_id', 2673373, 'resumes_block_id', 2673374)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9852, 'question_id', 'q2', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Obtain a legible official copy of this same notification page and compare the obscured label directly; never infer it from neighbouring enumerators or substitute a different version.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 12543
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 12543);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 12543) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 12543: run tools/record_source_refetch.py --observation 12543 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 12543;
