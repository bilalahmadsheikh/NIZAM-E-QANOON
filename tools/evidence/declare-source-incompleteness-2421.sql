-- DRAFT (agent JA, 13 Oct 2026, PREPARE MODE -- not run). Document 2421: section 16 is not printed in this copy;
-- the owner chose to release the Act with the gap recorded as source incompleteness (migration 0054).
-- Pattern: tools/evidence/declare-source-incompleteness-1121.sql (and -510).
--
-- Document 2421, The Balochistan University of Information Technology, Engineering & Management Sciences
-- (Amendment) Act, 2015 (Act No. XII of 2015). Observation 1370,
-- http://balochistancode.gob.pk/lawdir/fe766e67-1241-46fc-ad5a-ad248e2dfbba.pdf,
-- SHA-256 9452f8ce3cbd3521bccc967199d2d25c2149d62292d77048ae2240aa63f76945, eighteen pages.
--
-- Owner decision: decision-review-2026-10-12-j.json, document 2421, q1, choice "release-with-gap"
-- ("Release; record section 16 as not printed in the copy"): sections 1-15 and 17 onwards are released as
-- printed; section 16 is recorded as source incompleteness, so nothing is cited for it.
--
-- Read from the renders (agent JA, 13 Oct 2026): p14 (eaabe1ce...) '15. In the said Ordinance, for section 22,
-- the following shall be substituted ...'; p15 (5f3c502e...) the substituted s.22's clauses (i)-(m) end with
-- '(m) perform such functions as may be prescribed by Regulations.' and the page continues '17. In the said
-- Ordinance, in section 27, for the word "Syndicate" wherever it appears, the word "Senate" shall be
-- substituted.' (margin 'Amendment of Section 27, Ordinance XI of 2002.'). No '16.' is printed on any of the
-- eighteen pages; the copy prints no contents list.
--
-- ORDER (as for 510/1121, migration 0060):
--   1. python tools/record_source_refetch.py --observation 1370 --apply  (a dated refetch of the official URL).
--      If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first -- this file then
--      refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: the copy prints no contents list.
--
-- Idempotent: a second run inserts nothing once a record stands for 1370.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 1370 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 1370 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 1370, 2421, 'no_complete_copy_acquired', NULL,
       'Page 15 prints the end of section 15 (clause (m) of the substituted section 22) and then "17."; '
       'no section 16 is printed on pages 1-18.',
       'Section 16 of the Balochistan University of Information Technology, Engineering & Management Sciences '
       '(Amendment) Act, 2015, which the body''s numbering 1-15, 17-24 implies but this copy does not print.',
       'All eighteen rendered pages read. p14: "15. In the said Ordinance, for section 22, the following shall be '
       'substituted ..."; p15: the substituted section 22''s clauses (i)-(m), then "17. In the said Ordinance, in '
       'section 27, for the word \"Syndicate\" wherever it appears, the word \"Senate\" shall be substituted." '
       'beside the margin note "Amendment of Section 27, Ordinance XI of 2002."; a text search of every block '
       'finds no "16."; the copy prints no contents list. Nothing is inferred for section 16 and nothing is cited '
       'for it (owner, 2026-10-12 export j q1).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same eighteen-page PDF '
                 '(SHA-256 9452f8ce...); no copy printing section 16 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing section 16 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '9452f8ce3cbd3521bccc967199d2d25c2149d62292d77048ae2240aa63f76945',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2421-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2421-p14.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2421-p15.png'),
         'render_sha256', jsonb_build_array(
           '264f9001fc1f7f79423329c62532d57eae852c7f3ec8fe3166414b2e7332865f',
           'eaabe1ce4dc3e35f34478f96b00edaab4ebffa37e21ed3c3f7b2cb581ad25398',
           '5f3c502e466702fa415d41f69a4ee80236a8c109319f6150b46dbc902c5cf378'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'section 16',
                              'between', 'section 15 (p14-15, ends block 198896) and section 17 (p15, block 198897)')),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 2421, 'question_id', 'q1', 'choice', 'release-with-gap'),
         'release_note', 'Released at owner direction with sections 1-15 and 17-24 as printed; section 16 is not '
                         'printed in this copy and is not fabricated, inferred or cited.',
         'recovery_path', 'find the Balochistan Gazette (Extra-ordinary) of 12 October 2015 printing Act No. XII of '
                          '2015, then recover_acquisition.py --alternate-for 1370 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 1370
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 1370);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 1370) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 1370: run '
                        'tools/record_source_refetch.py --observation 1370 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 1370;
