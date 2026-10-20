--
-- Document 1247, THE SINDH SOLID WASTE MANAGEMENT BOARD ORDINANCE, 2013 (Sind
-- Ordinance No. 1 of 2014): the landed copy does not print section 15.
--
-- Observation 3964, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000065.pdf,
-- SHA-256 20743625d50bf2553557e6a4f341557ff62d5c1be9e2a213234b3c89b362b7b3, eighteen pages.
--
-- Owner decision: decision-review-2026-10-07-e.json, document 1247, q1,
-- choice "release-with-gap" (reviewer Bilal Ahmad, page images reviewed):
-- release ss.1-14 as printed and record contents row 15 "Repeal." as source
-- incompleteness, shown as not available in this copy -- never as repealed
-- or absent.
--
-- Read from the renders on 2026-10-08 (agent CA): pages 1-2 are the contents,
-- which list Chapters I-VIII and sections 1-15, ending '14. Decisions.' and
-- '15. Repeal.' (p2) with no [Omitted] or [Repealed] mark. The body prints the
-- title, date '[8th January, 2014]', long title, preamble and enacting formula
-- (p3) and ss.1-14 (pp3-18); s.14 (Chapter VIII, Miscellaneous) prints (1)-(3)
-- on p17 and (4)-(5) on p18, and the copy ends there: the rest of p18 below
-- '(5) Any action taken by the employee of the Board in good faith shall not be
-- questioned in any court of law.' is blank and there is no page 19. No
-- section 15, stub, omission mark or footnote anywhere.
--
-- Resolution 'no_complete_copy_acquired': no complete copy of the Ordinance is
-- in the corpus. Document 1233 is the SINDH SOLID WASTE MANAGEMENT BOARD ACT,
-- 2014, a different instrument whose own s.15 reads 'The Sindh Solid Waste
-- Management Board Ordinance is hereby repealed.'; it is evidence of what
-- followed the Ordinance, not a copy of the Ordinance's s.15.
--
-- A dry run of tools/record_source_refetch.py --observation 3964 on 2026-10-08
-- returned HTTP 200, 108208 bytes, SHA-256 20743625... = the held blob
-- ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 3964 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal
--      serves the same bytes, otherwise the error it gave). If it reports a
--      DIFFERENT valid PDF it records nothing: land and read that copy first --
--      this file then refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   3. tools/adjudicate_toc_from_source.py with the contents reading
--      (.artifacts/release-work-2026-09-24/claude/agCA/toc-1247-DRAFT.json),
--      naming the id this file prints as source_incompleteness_id and the
--      toc_entry_id of row 15 re-read after the replay.
--
-- Idempotent: a second run inserts nothing once a record stands for 3964.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 3964 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 3964 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 3964, 1247, 'no_complete_copy_acquired', NULL,
       'Page 18 of 18 ends with section 14(5); the rest of the page is blank and section 15 is not printed anywhere.',
       'Contents row 15 "Repeal." (page 2), after "14. Decisions." under Chapter VIII Miscellaneous.',
       'All eighteen rendered pages read. The contents (pp1-2) list Chapters I-VIII and sections 1-15, ending '
       '"14. Decisions." and "15. Repeal." with no [Omitted] or [Repealed] mark. The body prints the title, date '
       '"[8th January, 2014]", long title, preamble and enacting formula (p3) and sections 1-14 (pp3-18); section 14 '
       'prints (1)-(3) on p17 and (4)-(5) on p18, the last line being "(5) Any action taken by the employee of the '
       'Board in good faith shall not be questioned in any court of law." Below it p18 is blank but for the page '
       'number, and there is no further page. No section 15, stub, omission mark or footnote appears. The later '
       'Sindh Solid Waste Management Board Act, 2014 (doc 1233) is a different instrument; its own s.15 repeals '
       'this Ordinance.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same eighteen-page PDF '
                 '(SHA-256 20743625...); no copy printing section 15 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing section 15 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '20743625d50bf2553557e6a4f341557ff62d5c1be9e2a213234b3c89b362b7b3',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc1247-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1247-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1247-p17.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1247-p18.png'),
         'render_sha256', jsonb_build_array(
           'd3bb5d9aba18da470513783d5d5e880480e521b81f014d959653d164ac955fa6',
           'e48631ee12721fe60a31f1a8614b5508e1990387ba096b1d276ce260bacf6aa0',
           'e90258e4d0ce87ec65126cb761c1a42c468f8a514804d63fd8def9e03c134e71',
           '0b5184fe8d66dab1259b00d31a8164ca695746fcb921a7d0a846e073c27d4619'),
         'missing_contents_rows', jsonb_build_array(jsonb_build_object(
           'printed_label', '15', 'printed_heading', 'Repeal.', 'contents_page', 2,
           'contents_source_block_id', 65550)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-07-e.json',
           'document_id', 1247, 'question_id', 'q1',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; '
                         'section 15 is not fabricated and is not recorded as repealed or absent.',
         'recovery_path', 'retry sindhlaws.gov.pk or find a Gazette copy of Sind Ordinance No. 1 of 2014, then '
                          'recover_acquisition.py --alternate-for 3964 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 3964
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 3964);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 3964) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 3964: run '
                        'tools/record_source_refetch.py --observation 3964 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

-- The id to name as source_incompleteness_id in the contents reading.
SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 3964;
