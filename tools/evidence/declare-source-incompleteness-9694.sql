--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9694, The Agricultural Produce Markets Act, 1939 and Rules, 1940 (Sind compilation, Bureau of Supply and Prices).
-- Observation 9776, https://sindhlaws.gov.pk/setup/Publications/PUB-21-000056.pdf, SHA-256 3247902ed41e0cf17b41240be93d9a0bb242ff02f27e8f9b6c94739497afdab8.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9694, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 9776 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 9776 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 9776 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 9776, 9694, 'no_complete_copy_acquired', NULL,
       'The landed copy BEGINS late: scan 1 is the cover, scan 2 the Act''s contents list (sections 1-17), and scan 3 opens inside the definition of ''grower'' (section 2(c): ''Provided that no person shall be disqualified from being a grower ...''). The pages printing section 1 (Short title and extent) and the first part of section 2 (Definitions, clauses (a)-(c)) are not in the file.',
       'The contents list promises section 1 (Short Title and Extent, page 1) and section 2 (Definition, page 1), and the text of both up to clause (c) of section 2.',
       'The owner read all 22 scans against their images; scan 3''s first printed line is the continuation of a proviso inside section 2(c), and no earlier body page exists in the file. A dated refetch of the official URL (acquisition_attempt 220, 7 November 2026) returned the identical PDF (SHA-256 3247902e...). Nothing was supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 3247902e...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '3247902ed41e0cf17b41240be93d9a0bb242ff02f27e8f9b6c94739497afdab8',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9694-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9694-p3.png'),
         'render_sha256', jsonb_build_array('f8c7800508b67cc136c222d854ed623d433db5ac745f049d2f88b662d98c1a72', '2d0bd850a690953c94230b38605f222dea1e27e3b71de40461129278fa86566e'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Section 1 and the opening of section 2 (clauses (a), (b) and the start of (c)): not printed in the landed copy, which begins inside section 2(c).', 'last_printed_block_id', NULL, 'resumes_block_id', 2622502)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9694, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire a complete copy of the Agricultural Produce Markets Act, 1939 as applicable in Sind that includes the Act''s first pages (the Sindh Laws portal copy PUB-21-000056.pdf begins inside section 2); read it before adding section 1 and section 2(a)-(c). Preserve this source and declaration; no external wording used in this release.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 9776
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9776);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9776) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 9776: run tools/record_source_refetch.py --observation 9776 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 9776;
