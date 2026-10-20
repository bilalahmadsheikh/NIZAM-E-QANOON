-- Drafted by agent JF (17 Oct 2026); copied and applied by the owner-run batch. Revises agent JC's draft of 12 Oct
-- (tools/evidence/declare-source-incompleteness-3533-DRAFT.sql): cites owner export m, records the two released sibling
-- copies, and assumes the refetch step takes its URL from the scraper manifest (agent K4's staged diff
-- claude/agK4/staged/record-source-refetch-manifest-url.diff, sha faebfd95 -- NOT YET PORTED; builder BZ ports it with
-- its tests before this file can run). Pattern: declare-source-incompleteness-4646.sql / -510.sql.
--
-- Document 3533, stored title the placeholder 'document 3533'; the copy prints THE [PROVINCIAL] EMPLOYEES' SOCIAL
-- SECURITY ORDINANCE, 1965 (W.P. Ordinance X of 1965) [17th May, 1965] -- a Pakistan Code copy (watermark "THE
-- PAKISTAN CODE"), 32 pages. The contents (p5) ends '82. Repeal.', '83. Savings.', '84. Repeal.'; the body ends at
-- s.82 on p32 ('82. Repeal.- The Employees' Social Insurance Ordinance, 1962 ... is hereby repealed.' and a rule).
--
-- Observation 370 (source_id pk-federal), SHA-256 7c62b3e7afd82f5707e348d91b9b1927e1d096102b364a98c93bb15416c06cd1,
-- landed with NO canonical_url (landing defect: the zip entry prints '_' for the apostrophe, so no manifest row matched;
-- agent K4, claude/agK4/3533-url-evidence.json). The archive manifest row whose sha256 is the held blob names
-- pdf_url https://pakistancode.gov.pk/pdffiles/administratora522f8db17a8fa28b29b5444ded32b3c.pdf.
--
-- Owner decision: .artifacts/decision-review/exports/decision-review-2026-10-16-m.json, document 3533, q1
-- 'release-with-gap' (card d11fba63..., reviewed_page_images true; the same answer as export j): the Ordinance releases
-- with ss.1-82; ss.83 'Savings.' and 84 'Repeal.' are recorded as source incompleteness (named in the contents, not
-- printed).
--
-- FLAG (agent K4, checked by JF on the database 17 Oct): the two RELEASED sibling copies of this Ordinance -- doc 2119
-- (Balochistan Code, 43 pp) and doc 4327 (Punjab Code, 34 pp) -- have contents ledgers that end at row '82 Repeal.';
-- only this Pakistan Code copy's contents adds rows 83-84. The record below says so in `observed`; it does not decide
-- whether ss.83-84 exist.
--
-- Read from the renders (agent JC 12 Oct; agent JF 17 Oct): p5 (69f8f163...) contents rows 82-84; p6 (7d15dd72...)
-- title, preamble, Chapter I; p32 (82c40c89...) s.82 and the closing rule, nothing after.
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 370 --manifest-archive "<the Federal Laws zip>"
--        --manifest "Federal Laws/output/manifest.csv"   (dry run; --apply only if it is unchanged_copy)
--   2. this file. It refuses unless step 1's attempt exists.
--   3. contents rows 83/84 'source_incomplete' (claude/agJF/toc-3533-DRAFT.json, filled after the replay).
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
       'is hereby repealed." and a closing rule. No s.83 or s.84, stub, omission mark or footnote appears. The two '
       'released sibling copies of the Ordinance (doc 2119, Balochistan Code; doc 4327, Punjab Code) have contents that '
       'end at row 82 "Repeal."; only this copy''s contents names rows 83 and 84.',
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
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json',
           'card_sha256', 'd11fba63af651e91ee967be668d0ed9fcc939595df5d10a8dea4003879e0b558',
           'document_id', 3533, 'question_id', 'q1',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; '
                         'ss.83-84 are not fabricated and are not recorded as repealed or absent.',
         'sibling_copies', jsonb_build_array(
           jsonb_build_object('document_id', 2119, 'contents_last_row', '82 Repeal.'),
           jsonb_build_object('document_id', 4327, 'contents_last_row', '82 Repeal.')),
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
                        '--manifest-archive ... --manifest ... --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 370;
