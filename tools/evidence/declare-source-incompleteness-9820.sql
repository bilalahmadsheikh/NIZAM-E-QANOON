--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 9820, The Panjab District Boards Act, 1883 (Act No. XX of 1883).
-- Observation 10667, https://drs.molaw.gov.pk/pdf/XX.%20The%20Panjab%20District%20Boards%20Act%2C%201883.pdf, SHA-256 6efc46aa500a990cfee3f66925c47c18dfefc29cfa3f1ecad6c348fd2d93aad3.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9820, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10667 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10667 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10667 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10667, 9820, 'no_complete_copy_acquired', NULL,
       'PDF page 3 (Gazette of India, 20 October 1883, p. 241): the left column is curled into the binding, so the opening of nearly every line is lost, including the printed numbers of sections 5, 6, 8 and 9 (section 7''s number survives).',
       'Section numbers 5, 6, 8 and 9 and the words lost at the line openings of Chapter II (contents rows 5, 6, 8 and 9 on PDF page 1).',
       'All twelve rendered pages read. The text of sections 5, 6, 8 and 9 is read where it is visible, with each lost word marked [illegible]. Because their printed numbers are not visible, the text stays under the preceding numbered unit (Chapter II''s opening and section 7). Contents rows 5, 6 and 8 cannot be bound to a printed section and are closed as source-incomplete; row 9''s own number is lost on the contents page too. Nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 6efc46aa...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '6efc46aa500a990cfee3f66925c47c18dfefc29cfa3f1ecad6c348fd2d93aad3',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc9820-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p5.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p6.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p7.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p8.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p9.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p10.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p11.png', '.artifacts/release-work-2026-09-24/claude/renders/doc9820-p12.png'),
         'render_sha256', jsonb_build_array('45097ae4d068248c06bc18adf757d061c997fada256817bf23ec1dc2ad987b27', 'e0cdaa25966c897d7defbf46a956ef356dbd38d28fa8db522645412eb8cb1c95', '22f6ad058bba0bfd2584605b2d9160fd32fc098b9db5ccfbd39943307924f7ff', 'b7f5953a772fd77efe974e98db25eb88ecc08c5f1165ab236fef201ce7b1f937', '5aac4df7fce618028aaf4d323899646f6b48dde016c2944917276bb3d00fc059', '2ef3270d766e5ec3e4934a721c1480f9e809f48db06003be02918fa3066ab50c', '6de5fbbf7d9890b61e6218bb8b552b319c4f12353b08cf5e413a667176e66877', '241fb65f7fbbb222dbb3f28f4a12a91062214509aa03008444d3db2983ef12b0', 'de17c21e1d3d21001326eea669bad2d87f344aec85a84ee800a11adc1787e161', '9bcba6a5e719439946819602d4e2b7a16e052e1f123c39df96007ff01144af5b', '7d11ab2484a277dc2430bcc5512da01fb5743b2592b47bb01c78f4071fa535bc', 'b95859204c70acf97f034a177bddc9e003e278ebb8b857b9caa9c1a7f3c60a6b'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'the printed section numbers of sections 5, 6, 8 and 9, and the opening words of most lines in the left column of printed page 241, lost in the binding', 'last_printed_block_id', 2664187, 'resumes_block_id', 2664203)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9820, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find a clean print of Act No. XX of 1883 (Gazette of India, 20 October 1883 Part IV pp. 241-250, or the Panjab Code) and recover_acquisition.py --alternate-for the 9820 observation --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10667
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10667);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10667) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10667: run tools/record_source_refetch.py --observation 10667 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10667;
