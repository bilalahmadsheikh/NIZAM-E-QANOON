--
-- DRAFT by agent JC (12 Oct 2026, prepare mode; NOT RUN). Pattern: declare-source-incompleteness-510.sql.
--
-- Document 3533, stored title the placeholder 'document 3533'; the copy prints THE [PROVINCIAL] EMPLOYEES' SOCIAL
-- SECURITY ORDINANCE, 1965 (W.P. Ordinance X of 1965) [17th May, 1965] -- a Pakistan Code copy (watermark "THE
-- PAKISTAN CODE"), 32 pages. The contents (p5) ends '82. Repeal.', '83. Savings.', '84. Repeal.'; the body ends at
-- s.82 on p32 ('82. Repeal.- The Employees' Social Insurance Ordinance, 1962 ... is hereby repealed.' and a rule).
--
-- Observation 370 (source_id pk-federal), SHA-256 7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1.
-- !! STEP 1 CANNOT RUN AS WRITTEN: observation 370 has NO canonical_url (it was landed from the archive,
--    source_metadata.archive_path 'Federal Laws/output/1965/Provincial Employees_ Social Security Ordinance, 1965.pdf'),
--    so tools/record_source_refetch.py has no official URL to ask again, and source_incompleteness (0054) needs
--    attempts_considered >= 1 with evidence.attempt_ids. The lead must first find the Pakistan Code URL of this
--    Ordinance (or decide how an archive-only observation's attempt is recorded) -- see agJC-log.md.
--
-- Owner decision: decision-review-2026-10-12-j.json, document 3533, q1 'release-with-gap' (reviewer Bilal Ahmad):
-- the Ordinance releases with ss.1-82; ss.83 'Savings.' and 84 'Repeal.' are recorded as source incompleteness
-- (named in the contents, not printed).
--
-- Read from the renders on 2026-10-12 (agent JC): p5 (69f8f163...) contents rows 82-84; p6 (7d15dd72...) title,
-- preamble, Chapter I; p32 (82c40c89...) s.82 and the closing rule, nothing after. All 32 pages rendered.
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 370 --apply   (needs a URL first -- see above)
--   2. this file. It refuses unless step 1's attempt exists.
--   3. tools/adjudicate_toc_from_source.py --readings .artifacts/release-work-2026-09-24/claude/agJC/toc-3533-DRAFT.json
--      (fill toc_entry_id after the replay and source_incompleteness_id with the id this file prints).
--
-- Idempotent: a second run inserts nothing once a record stands for 370.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 370 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 370 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 370, 3533, 'no_complete_copy_acquired', NULL,
       'Page 32 prints s.82 "Repeal." and a closing rule; sections 83 and 84 are not printed anywhere in the 32 pages.',
       'Contents rows "83. Savings." and "84. Repeal." (page 5), after "82. Repeal."',
       'All 32 rendered pages available; pages 5, 6 and 32 read for this record. The contents (p5) ends "82. Repeal.", '
       '"83. Savings.", "84. Repeal." with no [Omitted] or [Repealed] mark. The body ends on p32 with "82. Repeal.- The '
       'Employees'' Social Insurance Ordinance, 1962 (XXII of 1962), in its application to the Province of West Pakistan, '
       'is hereby repealed." and a closing rule. No s.83 or s.84, stub, omission mark or footnote appears.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch returned the same 32-page PDF (SHA-256 7c62b3e7...); no copy printing ss.83-84 was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing ss.83-84 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3533-p5.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3533-p6.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3533-p32.png'),
         'render_sha256', jsonb_build_array(
           '69f8f16395f1b52257f2c6b0f78dc519303db1f7e08430264648be0f83a47f7d',
           '7d15dd725b871d267d7ebdc2b0d5dc60ec95b2202cd37709d56e4d1a82127b2e',
           '82c40c8949ca8b9fd08ddd420e309bcea2a04f03282e8506e3dd3cc46dff584f'),
         'missing_contents_rows', jsonb_build_array(
           jsonb_build_object('printed_label', '83', 'printed_heading', 'Savings.', 'contents_page', 5,
                              'contents_source_block_id', 403742),
           jsonb_build_object('printed_label', '84', 'printed_heading', 'Repeal.', 'contents_page', 5,
                              'contents_source_block_id', 403742)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 3533, 'question_id', 'q1',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; '
                         'ss.83-84 are not fabricated and are not recorded as repealed or absent.',
         'recovery_path', 'find the Pakistan Code (or Gazette) copy of W.P. Ordinance X of 1965 printing ss.83-84, '
                          'then recover_acquisition.py --alternate-for 370 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 370
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 370);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 370) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 370: run '
                        'tools/record_source_refetch.py --observation 370 '
                        '--apply first (observation 370 has no canonical_url)';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 370;
