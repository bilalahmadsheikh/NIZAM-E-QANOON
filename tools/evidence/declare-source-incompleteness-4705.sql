-- Lead, 20 Oct 2026. Pattern: declare-source-incompleteness-4594-DRAFT.sql (no_complete_copy_acquired, released with
-- the gap recorded). Document 4705 (4520's promoted revision; observation 1254, balochistancode.gob.pk lawdir
-- f0f1eced-...): the Information Department notification of Feb 2019, 'GUIDELINES / SOPS' OF JOURNALIST WELFARE FUND',
-- released 20 Oct 2026 as instrument 599338c1. Para 7 ('APPLICATION FORM') prescribes the application 'in the form
-- prescribed in Schedule-I.'; the file's last page (p5, numbered '(5)') ends with para 12, the signature and the Copy-to
-- list, and no Schedule-I is printed. Owner: 'release 4520 for what it actually is' (chat, 20 Oct 2026). Requires a dated
-- refetch (tools/record_source_refetch.py --observation 1254 --apply) first. Idempotent.
\set ON_ERROR_STOP on
BEGIN;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt WHERE source_observation_id = 1254 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 1254 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = 4705 AND is_active) THEN
        RAISE EXCEPTION 'document 4705 is not active';
    END IF;
END $$;
INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by)
SELECT 1254, 4705, 'no_complete_copy_acquired', NULL,
       'PDF page 5 (printed page number (5)) ends the notification: para 12 (AUTHORITY), the signature, "NO. Even Dated '
       'Even.", the Copy-to list 1-10 and the office endorsement of 19/2/19. No Schedule-I follows.',
       'Schedule-I: the application form para 7 prescribes ("in the form prescribed in Schedule-I.").',
       'All five pages read on their renders (claude/renders/doc4520-p1..p5) and through the owner-accepted Surya OCR '
       '(ocr-review-doc-4520.json, 5/5). Paras 1-12 are complete and release as printed; only the annexed form is absent.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same 5-page PDF; no copy printing Schedule-I was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing Schedule-I was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc4520-p3.png',
                                              '.artifacts/release-work-2026-09-24/claude/renders/doc4520-p5.png'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Schedule-I (the application form)',
                                                         'between', 'after p5, the last page of the file')),
         'gap_proof', jsonb_build_object('basis', 'para 7 (p3) cites Schedule-I; p5 numbered (5) closes the letter with '
                                                  'the Copy-to list; the file has 5 pages'),
         'refetch', jsonb_build_object('outcomes', jsonb_agg(DISTINCT outcome),
                                       'complete_copy_checked', bool_or(outcome = 'unchanged_copy'),
                                       'owed', NOT bool_or(outcome = 'unchanged_copy')),
         'owner_decision', jsonb_build_object('source', 'chat 20 Oct 2026: release 4520 for what it actually is',
                                              'plan', 'tools/evidence/multi-instrument-plans/doc-4705.json'),
         'pattern', jsonb_build_array(4594, 3533, 4575)),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 1254
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 1254);
COMMIT;
SELECT id, document_id, resolution, attempts_considered, observed_error FROM v_source_incompleteness_latest WHERE source_observation_id = 1254;
