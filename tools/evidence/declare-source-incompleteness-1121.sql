-- Document 1121: the "source defect" flag the owner asked for (export -e q1), in the vocabulary migration 0054
-- gives a landed copy that is not the whole instrument. Drafted by agent CB (8 Oct 2026); recorded by agent BZ
-- after the dated refetch (acquisition_attempt 148, unchanged_copy). Pattern:
-- tools/evidence/declare-source-incompleteness-510.sql.
--
-- Document 1121, RECRUITMENT RULES, 2009 (the Food Department, Office of the Cane Commissioner Punjab
-- Recruitment Rules, 2009). Observation 2026,
-- https://punjabcode.punjab.gov.pk/uploads/articles/recruitment-rules-2009-doc-pdf.pdf,
-- SHA-256 30dd3d87cc1d5566b0adb30fe3bd388164e64fb134b716baa25c80ff4cbf3d5f, five pages.
--
-- Owner decision: decision-review-2026-10-07-e.json, document 1121, q1, card
-- 175c79295026524215a092d31d975f25713931669848d18b0e8bde9cdbee6389, choice "release-as-is" (reviewer Bilal Ahmad):
-- "Release pp2-4 as the Food Department, Office of the Cane Commissioner Punjab Recruitment Rules, 2009,
-- represented by the titled recruitment table. The 2009 enacting notification is absent from this copy. The 2011
-- notification on p1 announces amendments but no amendment provisions follow; therefore no 2011 changes should be
-- inferred or applied. Treat p1 and the p5 distribution list as incomplete amendment apparatus and flag the
-- missing 2011 amendment text as a source defect."
--
-- Read from the renders on 2026-10-08 (agent CB): p1 (26362e51...) the S&GAD notification of 14 May 2011,
-- No.SOR-III(S&GAD)1-13/2009, ends "... in the Punjab Food Department, office of the Cane Commissioner
-- Recruitment Rules, 2009 the following amendments shall be made, namely:-" and the rest of the page is blank;
-- pp2-4 (4fd1c2fe..., 9afcde87..., 667ffd4d...) the title "THE FOOD DEPARTMENT, OFFICE OF THE CANE COMMISSIONER
-- PUNJAB RECRUITMENT RULES, 2009." over the ten-column recruitment table (20 post rows, Cane Commissioner (BS-19)
-- ... Sanitary Worker (BS-1)), then the signature "MUHAMMAD ILYAS / SECRETARY (REGULATIONS), S&GAD / Dated
-- Lahore, the 23th May, 2011"; p5 (ac3768d9...) the distribution list "No.SOR-III(S&GAD)1-3/2009 / A copy is
-- forwarded ... 6. The System Analyst (O&M Wing) ... with the request to incorporate the said amendment in the
-- database ...". No amendment text is printed anywhere, and the 2009 Rules' own enacting notification (the
-- rules giving title, commencement and the reference to the Schedule) is not printed either.
--
-- ORDER (as for 510, migration 0060):
--   1. python tools/record_source_refetch.py --observation 2026 --apply  (a dated refetch of the official URL).
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: the copy prints no contents list (toc_found false).
--
-- Idempotent: a second run inserts nothing once a record stands for 2026.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 2026 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 2026 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2026, 1121, 'no_complete_copy_acquired', NULL,
       'Page 1 prints the 14 May 2011 notification only to "... Recruitment Rules, 2009 the following amendments '
       'shall be made, namely:-"; the page is blank after it and no amendment is printed on pages 1-5.',
       'The amendments to the 2009 Recruitment Rules that the S&GAD notification No.SOR-III(S&GAD)1-13/2009 of '
       '14 May 2011 announces ("the following amendments shall be made, namely:-"); and the 2009 Rules'' own '
       'enacting notification, which this copy does not print.',
       'All five rendered pages read. p1: the 2011 notification opens and stops at "namely:-" (blank below). '
       'pp2-4: the title "THE FOOD DEPARTMENT, OFFICE OF THE CANE COMMISSIONER PUNJAB RECRUITMENT RULES, 2009." '
       'over the ten-column recruitment table, 20 unnumbered post rows, then the signature "MUHAMMAD ILYAS / '
       'SECRETARY (REGULATIONS), S&GAD / Dated Lahore, the 23th May, 2011". p5: the distribution list asking the '
       'O&M Wing "to incorporate the said amendment in the database". The amendments are never printed; nothing '
       'of them is inferred or applied, and the released Rules are the table as printed (owner, 2026-10-07 q1).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same five-page PDF '
                 '(SHA-256 30dd3d87...); no copy printing the 2011 amendments or the 2009 enacting notification '
                 'was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the 2011 amendments was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '30dd3d87cc1d5566b0adb30fe3bd388164e64fb134b716baa25c80ff4cbf3d5f',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc1121-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1121-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1121-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1121-p4.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1121-p5.png'),
         'render_sha256', jsonb_build_array(
           '26362e51fcafaca747d676ae84fd38ce372dac94f25b1bf5fb38518f023bc76d',
           '4fd1c2fe730391553e642e04bc6852cd8d00a17d1f0fb95ea350a31d96bad36e',
           '9afcde87502e0d4bdd479cf3508fa98bf4a007756a198b838648473dadf3514b',
           '667ffd4da850da1da416a8ed82a28266fe7b3fe4ab05365e8ed22de7b7895dd4',
           'ac3768d9f4476a7e828b38267d3ac5bdbdf4ee3e6476077d7ec4988fa5286e99'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', '2011 amendment text',
                              'announced_by', 'S&GAD notification No.SOR-III(S&GAD)1-13/2009, 14 May 2011, p1',
                              'source_block_id', 54425),
           jsonb_build_object('what', '2009 enacting notification of the Recruitment Rules, 2009')),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-07-e.json',
           'card_sha256', '175c79295026524215a092d31d975f25713931669848d18b0e8bde9cdbee6389',
           'choice', 'release-as-is', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction as the 2009 Rules held as the titled recruitment table; the '
                         '2011 amendments are not fabricated, inferred or applied, and p1/p5 are set aside as '
                         'apparatus.',
         'recovery_path', 'find the Gazette copy of the 14 May 2011 S&GAD notification No.SOR-III(S&GAD)1-13/2009 '
                          'and of the 2009 notification making the Rules, then recover_acquisition.py '
                          '--alternate-for 2026 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 2026
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2026);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2026) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 2026: run '
                        'tools/record_source_refetch.py --observation 2026 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 2026;
