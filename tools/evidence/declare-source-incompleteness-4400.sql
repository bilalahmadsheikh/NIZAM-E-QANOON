--
-- DRAFT by agent JE (13 Oct 2026, prepare mode; not run). Pattern: declare-source-incompleteness-1822.sql / -510.sql.
--
-- Document 4400, THE WEST PAKISTAN BUILDINGS & ROADS DEPARTMENT CODE (up-to-date amendments 1994). Observation 2311,
-- https://punjabcode.punjab.gov.pk/uploads/articles/west-pakistan-buildings-and-roads-department-code-doc-pdf.pdf,
-- SHA-256 8d57603421354711baa8155c7c2abf125d38574ceef1ee9287f32636a4a7050a, 315 pages.
--
-- Owner decisions (decision-review-2026-10-12-j.json, re-confirmed in -k.json; reviewer Bilal Ahmad):
--   q3 'range-notes': each printed omitted-range line is kept as a non-citable note, no paragraph stubs; paragraph 1.79
--      (neither printed nor declared omitted) and the backwards range '1.80 to 1.58' are recorded as source
--      incompleteness (migration 0054).
--   q4 'release-with-gap': the Code is released without Appendix III, which is recorded as source incompleteness; the
--      untitled Sanitary Rules on p286 are held as Appendix IV (the contents' order, p8 'IV. Sanitary rules on
--      Extensive Works.').
--
-- Read (agent JE, 13 Oct): p11 (renders/doc4400-p11.png a0457e3b...) the four range lines A-D under 'A—ORGANZATION'
-- ('Paragraphs 1-1 to 1-3 omitted.' ... 'Para1-23.to.1-37.omitted'); p18 (cbeef3f4...) after 1.70 'F—ALLOWANCE,
-- ADVANCES AND COMPENSATION.' / 'Paragraph 1.71 to 1.78 Omitted' / 'G—LEAVE' / 'Paragraph 1.80 to 1.58 Omitted.' /
-- 'H—EXAMINATIONS' / 'I—TRAINING AND EXAMINATION OF ENGINEERS'; p19 (74e407d1...) paragraph 1.86 follows -- no 1.79
-- anywhere; p7-8 (contents) 'APPENDICES I. ... II. ... III. List of Periodical Returns.' and 'IV. Sanitary rules on
-- Extensive Works.' ... 'VII.'; p285 (417952fc...) the end of Appendix II's table (items 69-72); p286 (3e5fad92...)
-- '(REFERRED TO IN PARAGRAPH 2.101)' / 'Sanitary Rules, on Extensive Works' with no APPENDIX heading; p289 (a4d1fa57...)
-- 'APPENDIX V'. Appendix III is printed nowhere in the copy.
--
-- ORDER: 1. python tools/record_source_refetch.py --observation 2311 --apply (a different valid PDF -> read it first);
--        2. this file (refuses without step 1's attempt). The contents is held as a region with rows 'none'
--        (rule reviewed_contents_region), so no contents row is left pending by the gaps.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 2311 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 2311 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2311, 4400, 'no_complete_copy_acquired', NULL,
       'Three internal gaps; the body itself runs to its end. (1) Chapter I, p18: after "Paragraph 1.71 to 1.78 Omitted" '
       'the copy prints "Paragraph 1.80 to 1.58 Omitted." (a range that runs backwards) and then paragraph 1.86 (p19); '
       'paragraph 1.79 is neither printed nor declared omitted. (2) Appendices, pp285-289: Appendix II ends on p285 and '
       'the untitled "(REFERRED TO IN PARAGRAPH 2.101) Sanitary Rules, on Extensive Works" (held as Appendix IV) begins '
       'on p286; Appendix III is not printed.',
       'Paragraph 1.79 (Chapter I, under G—LEAVE, whose printed range is misprinted "1.80 to 1.58"); Appendix III, '
       '"List of Periodical Returns." (contents p7).',
       'All 315 pages are in the copy; the pages named here were read from the renders. The contents (pp1-8) prints '
       'paragraph ranges, not rows. Chapter I declares paragraphs 1.1-1.37 omitted by four range lines (p11), 1.71-1.78 '
       '(p18) and "1.80 to 1.58" (p18); 1.79 falls in no printed range and is not printed. The contents lists '
       'Appendices I-VII; the body prints I, II, the untitled Sanitary Rules (the contents'' IV), V and onward, and no '
       'Appendix III. Owner q3 "range-notes" and q4 "release-with-gap": nothing is reconstructed; each range line is '
       'kept as printed.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same 315-page PDF (SHA-256 8d576034...); no copy '
                 'printing paragraph 1.79 or Appendix III was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing paragraph 1.79 or Appendix III was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '8d57603421354711baa8155c7c2abf125d38574ceef1ee9287f32636a4a7050a',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p8.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p11.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p18.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p19.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p285.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p286.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4400-p289.png'),
         'render_sha256', jsonb_build_array(
           '5e62e9b08e53e2b0fffcb7b8d9a27fe900bc3dc8e4bb79eb4ca69597555d6611',
           'a0457e3b3cfcc6d011fe811430d288bc6b7a2629b69c299e2e03508b10226a87',
           'cbeef3f430508d14894730477a07ee265a06bd81e38fc8252bf3dbd92cb2a93d',
           '74e407d1305301946478ebfcedd5c8ed93ac45510e7e07130987abc3c4b7e5c1',
           '417952fc60f5b1c203a11f7761de38ab610311d481c0ce2e1303f0f3ca5732dd',
           '3e5fad92bb9dc63bebc834567c53d11e4d16e417af97b0e90f07ee3a5a01b497',
           'a4d1fa57821aa10282b4b101b159793f73ffc7fff646ef95d62f0ef7fea4a5f5'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'paragraph 1.79', 'printed_range_lines', jsonb_build_array(741818, 741820)),
           jsonb_build_object('what', 'Appendix III, List of Periodical Returns', 'contents_row_block', 741715,
                              'between_blocks', jsonb_build_array(745464, 745465))),
         'owner_decision', jsonb_build_array(
           jsonb_build_object('export', '.artifacts/decision-review/exports/decision-review-2026-10-12-k.json',
                              'document_id', 4400, 'question_id', 'q3', 'choice', 'range-notes', 'reviewer', 'Bilal Ahmad'),
           jsonb_build_object('export', '.artifacts/decision-review/exports/decision-review-2026-10-12-k.json',
                              'document_id', 4400, 'question_id', 'q4', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'))),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 2311
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 2311);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 2311) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 2311: run tools/record_source_refetch.py --observation 2311 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 2311;
