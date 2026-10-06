-- Document 510, THE SIND LOANS FOR AGRICULTURAL PURPOSES ACT, 1974 (Sind Act
-- XXII of 1974): the landed copy does not print section 4.
--
-- Observation 3151, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-15-000318.pdf,
-- SHA-256 3a7bb000f3ea56a154e556e32b183180156ae484f8c55f393f5b03ff56b58086, four pages.
--
-- Owner decision: decision-review-2026-10-06-b.json, document 510, q1,
-- card 7e28d4956aacd77cdcec7227250c02203b0de228cab61e2977c037298d622f09,
-- choice "release-with-gap" (reviewer Bilal Ahmad, page images reviewed):
-- release ss.1-3 and 5-10 as printed and record contents row 4 "Pass Book." as
-- source incompleteness, shown as not available in this copy -- never as
-- repealed or absent.
--
-- Read from the renders on 2026-10-06 (agent AW; re-checked by BX1): page 1's
-- contents lists 1-10 with "4. Pass Book." unmarked; page 3 prints s.2(h), (i),
-- (2), section 3, and then directly "5. (1) The borrower may deliver
-- agricultural produce ...", ss.6-7; page 4 prints ss.8-10 and ends. No section
-- 4, stub, omission mark or footnote anywhere. Section 2(g) defines
-- "pass-book" and section 6 requires payments to be "entered in the pass-book
-- of the borrower", so the Act has the section this copy omits.
--
-- Resolution 'no_complete_copy_acquired': no complete copy is in the corpus.
-- Document 791 is the Sind Loans for Agricultural Purposes ORDINANCE, 1974,
-- which section 10 of this Act repeals; its own s.4 on pass-books is evidence
-- that the Act's s.4 exists, not a copy of the Act.
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 3151 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal
--      serves the same bytes, otherwise the error it gave). If it reports a
--      DIFFERENT valid PDF it records nothing: land and read that copy first --
--      this file then refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   3. tools/adjudicate_toc_from_source.py with the contents reading, naming
--      the id this file prints as source_incompleteness_id.
--
-- Idempotent: a second run inserts nothing once a record stands for 3151.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 3151 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 3151 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 3151, 510, 'no_complete_copy_acquired', NULL,
       'Page 3 prints section 3 and then section 5; section 4 is not printed anywhere in the four pages.',
       'Contents row 4 "Pass Book." (page 1), between "3. Act to Override Laws." and "5. Delivery of agricultural produce."',
       'All four rendered pages read. The contents (p1) lists sections 1-10 including "4. Pass Book." with no '
       '[Omitted] or [Repealed] mark. The body prints ss.1-3 (pp2-3), then directly "5. (1) The borrower may '
       'deliver agricultural produce ..." (p3), ss.6-7 (p3) and ss.8-10 (p4), and ends. No section 4, stub, '
       'omission mark or footnote appears. s.2(g) defines "pass-book" and s.6 requires payments to be "entered '
       'in the pass-book of the borrower", so the Act has a pass-book section this copy omits; the repealed '
       'Ordinance (doc 791) prints its own s.4 on pass-books.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same four-page PDF '
                 '(SHA-256 3a7bb000...); no copy printing section 4 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing section 4 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '3a7bb000f3ea56a154e556e32b183180156ae484f8c55f393f5b03ff56b58086',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc510-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc510-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc510-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc510-p4.png'),
         'render_sha256', jsonb_build_array(
           '4621dea9be5e62d6605e9b4cab36e8e73250e14736a38e9ecc0af6865e56a5f9',
           '712373ce1f4d65245eee6a97c78f5c77fe331415200dfb701ee01615bd2835da',
           '5dc90c6cc7f0cd912ad67a3d3f569cf8698fc2e2f96428cc39da88e0e2f1657e',
           '32834a8001db52e04121a77cf7155515960ab376a82af4360b1f669004714d49'),
         'missing_contents_rows', jsonb_build_array(jsonb_build_object(
           'printed_label', '4', 'printed_heading', 'Pass Book.', 'contents_page', 1,
           'contents_source_block_id', 19681)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-06-b.json',
           'card_sha256', '7e28d4956aacd77cdcec7227250c02203b0de228cab61e2977c037298d622f09',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; '
                         'section 4 is not fabricated and is not recorded as repealed or absent.',
         'recovery_path', 'retry sindhlaws.gov.pk or find a Gazette copy of Sind Act XXII of 1974, then '
                          'recover_acquisition.py --alternate-for 3151 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 3151
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 3151);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 3151) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 3151: run '
                        'tools/record_source_refetch.py --observation 3151 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

-- The id to name as source_incompleteness_id in the contents reading.
SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 3151;
