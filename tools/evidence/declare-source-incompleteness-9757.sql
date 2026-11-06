--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9757, The European British Minors Act, 1874 (Act No. XIII of 1874).
-- Observation 10698, https://drs.molaw.gov.pk/pdf/XIII-The%20European%20British%20Minors%20Act%2C%201874.pdf, SHA-256 a36528c2aaf5c165119df7be0091a3b0c12f2a655c07d0d673d28db56fe50f46.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9757, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10698 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10698 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10698 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10698, 9757, 'no_complete_copy_acquired', NULL,
       'PDF page 3 (printed page 3) ends in section 2 with the definition ''''Minor'''' means a person who has not completed the age of eighteen years; and the catchword ''''Guardian''''; the next PDF page is printed page 6, which opens with the last words of section 8 (''require, may be used for the respective purposes mentioned in such schedule.'').',
       'The rest of section 2 (from the definition of ''Guardian''), Part II''s heading and sections 3 to 7, and the opening of section 8 (contents rows 3 to 8), printed on pages 4 and 5.',
       'All eleven rendered pages read: the contents (pages i-ii), printed page 3 and printed pages 6 to 13. Printed pages 4 and 5 are not in this copy. The tail of section 8 at the top of printed page 6 cannot be attached to a printed section number and is set aside with the gap. Released under the owner''s delegation with the missing pages recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 a36528c2...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'a36528c2aaf5c165119df7be0091a3b0c12f2a655c07d0d673d28db56fe50f46',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9757-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p5.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p6.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p7.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p8.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p9.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p10.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9757-p11.png'),
         'render_sha256', jsonb_build_array('2cc1eeed5430a72b0fb453c9ec036a736be1b23ca5e282b332a92ef90bb9e8e0', 'c79ce26103100d0cfcadaab6b60ea475d5907f4dea3e05180be9a9a13a8f7f0e', '3339e8faf5665c2a70ea17f7efc168325f44a62637e94a7308c3c9e0e53ab34f', '8c311646f17e225c12aff5725efae1196cc3c7ad46ce231e1cc77d3c3829dcc3', '73e254594d4c63467155950fbe4b2c53e8afbcb72644dfbe6bd69d64f8bf8a7e', '53c7cab186383ee7355f64d12a81c7149de364415b8279a1ec0475003f396c46', '23f475885c9e1c0145b04786857822629080ab39e36e27560b0695c2332d2a43', '8915c3cc548cd7a657749503b5e6aee949685c60e09a5672b2c404179c0cc9ab', '4ed8e26aa6ef182e801b0730968c999ab9c65bcc86a850901ccae18540026efb', 'a5e79aebfa8a7846a32c729513850db75152b8f963a7d1de6aa5029bc2af0862', '165282ef8f865785a0c70e2836677e2870b28e04b66a2296ec2895a7d0b9ed6d'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'printed pages 4 and 5: the rest of section 2, Part II''s heading, sections 3-7 and section 8 up to its last lines (the tail of section 8 at the top of printed page 6 is set aside with it)', 'last_printed_block_id', 2642775, 'resumes_block_id', 2642785)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9757, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find a complete print of Act No. XIII of 1874 (the Gazette of India of December 1874, Part IV, or the Unrepealed General Acts volume) and recover_acquisition.py --alternate-for 10698 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10698
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10698);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10698) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10698: run tools/record_source_refetch.py --observation 10698 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10698;
