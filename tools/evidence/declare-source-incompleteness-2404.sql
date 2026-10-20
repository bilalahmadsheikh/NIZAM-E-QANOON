-- DRAFT (agent JA, 13 Oct 2026, PREPARE MODE -- not run). Document 2404: neither set of Rules prints its Schedule;
-- the owner chose to release rules 1-3 of each with the Schedules recorded as not in the copy (migration 0054).
-- Pattern: tools/evidence/declare-source-incompleteness-1121.sql (and -510).
--
-- Document 2404, observation 2503, https://punjabcode.punjab.gov.pk/uploads/articles/service-rules-pimpd-pdf.pdf,
-- SHA-256 8186ad0205f33818c93a69378e0c79eaab5f40d7fe5c4ce66cc8db1a7d6c4216, eight pages, held after the split
-- (split-doc-2404-boundaries-DRAFT.sql, plan doc-2404) as four instruments.
--
-- Owner decision: .artifacts/decision-review/exports/decision-review-2026-10-12-j.json, document 2404, q2, choice "release-with-gap" ("Release rules 1-3 of each; record the
-- Schedules as not in the copy"): both sets of Rules are released with rules 1-3; each missing Schedule is
-- recorded as source incompleteness; the 2012 amendments are released as printed.
--
-- Read from the renders (agent JA, 13 Oct 2026): p1 (f71923b8...) the 2007 Rules, rule 3 '... shall be as given
-- in the Schedule.', then signature and distribution list -- no Schedule; p2 (da6256fe...) the 2010 Rules, rule 3
-- '... shall be as given in the Schedule annexed with those rules.', then signature and distribution list -- no
-- Schedule; pp3-5 and pp6-8 the 2012 notifications, which print only the entries they insert 'after the existing
-- entries' of those Schedules (Research Officer, Research Assistant; Director Academic/Additional Chief Instructor,
-- Deputy Director (Administration), Accounts Officer).  Neither Schedule is printed on any of the eight pages.
--
-- ORDER (as for 510/1121, migration 0060):
--   1. python tools/record_source_refetch.py --observation 2503 --apply  (a dated refetch of the official URL).
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
-- Idempotent: a second run inserts nothing once a record stands for 2503.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 2503 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 2503 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2503, 2404, 'no_complete_copy_acquired', NULL,
       'Page 1 ends the 2007 Rules at rule 3 ("... shall be as given in the Schedule.") and page 2 ends the 2010 Rules '
       'at rule 3 ("... shall be as given in the Schedule annexed with those rules."); each is followed only by its '
       'signature and distribution list.',
       'The Schedule of the PIMPD/MPDD Recruitment Rules, 2007 and the Schedule of the Punjab Management and '
       'Professional Development Department (Miscellaneous Posts) Service Rules 2010, to which rule 3 of each refers '
       'and to which the 2012 notifications add entries "after the existing entries".',
       'All eight rendered pages read. p1: the 2007 Rules 1-3, signature, endorsement and distribution list; p2: the '
       '2010 Rules 1-3, signature, endorsement and distribution list; pp3-5 and pp6-8: the 16 Feb and 17 Aug 2012 '
       'amending notifications with only their inserted entries. Neither Schedule is printed; nothing of either is '
       'inferred or applied; the Rules are released with rules 1-3 (owner, 2026-10-12 export j q2).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same eight-page PDF '
                 '(SHA-256 8186ad02...); no copy printing either Schedule was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing either Schedule was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '8186ad0205f33818c93a69378e0c79eaab5f40d7fe5c4ce66cc8db1a7d6c4216',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc2404-p1.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p2.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p3.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p4.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p5.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p6.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p7.png', '.artifacts/release-work-2026-09-24/claude/renders/doc2404-p8.png'),
         'render_sha256', jsonb_build_array('f71923b814df45340e8e2693f57499bd6fbd8ec762542089ce15bb414841be04', 'da6256fe3fcfa9d8187518b9bc8ae3f9eef4cf15a95154508cf350d3bf4bd098', '26851785e8f9d6e92a5bea5ff51be0e05d75e9f8d440f9f7b21fae2ca68c4745', '1dd0d22c20f2cafa735a4758a5ccc4e61de2fb56e0ee5c96d321b7c19e2d8fb5', '36de1e80b1a4f494a5a378ec98951bf368e65730fe9807d5fe0f3ada280e4587', 'd44a66f63f90345bbe812b7a9c848fbd4385b19c101215366da4b2d118a88349', '7b1aa0e654219c7470292b8aa524181badc7ce9b954484f37595ccad899fc94d', '5eda60674b9a848480f4e5097a4b07fdf6ac2010402dd5589fffc54cd3199bba'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'Schedule of the 2007 Recruitment Rules',
                              'referred_by', 'rule 3 of the 2007 Rules, p1', 'source_block_id', 196942),
           jsonb_build_object('what', 'Schedule of the 2010 Service Rules',
                              'referred_by', 'rule 3 of the 2010 Rules, p2', 'source_block_id', 196954)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json', 'document_id', 2404, 'question_id', 'q2', 'choice', 'release-with-gap'),
         'release_note', 'Released at owner direction: rules 1-3 of each set of Rules and the two 2012 amending '
                         'notifications as printed; the two Schedules are not printed in this copy and are not '
                         'fabricated, inferred or applied.',
         'recovery_path', 'find the Punjab Gazette prints of the 2007 Recruitment Rules and the 2010 Service Rules '
                          'with their Schedules, then recover_acquisition.py --alternate-for 2503 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 2503
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2503);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2503) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 2503: run '
                        'tools/record_source_refetch.py --observation 2503 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 2503;
