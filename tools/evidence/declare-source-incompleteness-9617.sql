--
-- By Codex (8 Nov 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9617, Rules for the Examination of Masters and Mates.
-- Observation 13092, https://drs.molaw.gov.pk/pdf/Rules%20For%20The%20Examination%20Of%20Masters%20and%20Mates.pdf, SHA-256 f050ca25af9dcb85b404b9c4fce688baf523ecf8d8dcd15efa66c58c49c9ada1.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9617, q2
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 13092 --apply (done8Nov2026 acquisition_attempt223); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 13092 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 13092 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 13092, 9617, 'no_complete_copy_acquired', NULL,
       'All73 physical pages present; three damaged local text loci only.',
       'Eight chapters and Appendices A–F are present; preserve printed anomalous rule labels93/103 without inventing98/108.',
       'All73 original page images read. Three short damaged loci remain explicitly [illegible]: p29 rule102 internal4(c) after ascertain risk; p34 rule114(a) after rudder; p64 AppendixC Marks after each correct letter. Original300dpi crops independently reviewed; no word reconstructed. No missing pages or whole provisions alleged. Official refetch223 returned byte-identical30,679,937-bytePDF.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 f050ca25...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'f050ca25af9dcb85b404b9c4fce688baf523ecf8d8dcd15efa66c58c49c9ada1',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/codex-9617-2026-11-08/doc9617-p29.png', '.artifacts/release-work-2026-09-24/codex-9617-2026-11-08/doc9617-p34.png', '.artifacts/release-work-2026-09-24/codex-9617-2026-11-08/doc9617-p64.png'),
         'render_sha256', jsonb_build_array('a85f2b3530c28bbb229f83a434528b9af4c0f45be41fb4dc456fd9624054e51e', 'fd38b2a16c388ead47ad7516ad05f5903608750a099a734598782e7cdb514a98', 'da5a3c09dbb68993891f616a685b0a5cd67f5cf0acf0bc5bbaf9ff30f6b1d8f1'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'p29 rule102 internal4(c), short unreadable locus after ascertain risk before collision', 'last_printed_block_id', 2573816, 'resumes_block_id', 2573816), jsonb_build_object('what', 'p34 rule114(a), damaged word after rudder before transverse', 'last_printed_block_id', 2573940, 'resumes_block_id', 2573940), jsonb_build_object('what', 'p64 AppendixC Marks, damaged locus after each correct letter before numeral', 'last_printed_block_id', 2574560, 'resumes_block_id', 2574560)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9617, 'question_id', 'q2', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire a clearer official copy of these exact three loci and compare directly; never infer expected nautical vocabulary or import a different version.'),
       'codex.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 13092
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13092);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13092) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 13092: run tools/record_source_refetch.py --observation 13092 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 13092;
