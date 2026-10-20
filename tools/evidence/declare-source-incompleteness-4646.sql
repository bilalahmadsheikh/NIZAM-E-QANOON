-- Builder BZ (17 Oct 2026; applied by the owner-run batch, $S/agBZ-4646gap.sh). Pattern: declare-source-incompleteness-3577.sql.
--
-- Document 4646, the owner-accepted Surya OCR revision of 4522: THE SINDH HAZARDOUS OCCUPATIONS (SILICON) RULES, 2019
-- (Labour Department notification of 20 Feb 2020, Sindh Govt. Gazette of 7 May 2020, pp383-390), observation 4517
-- (canonical_url https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000023.pdf).
-- The rules cite 'the Schedule' -- defined in r.2(1)(h) '"Schedule" means the Schedule to these rules' and relied on by
-- r.1(2), r.8(1), r.12(1) and r.15(1)-(6) -- and 'a certificate of fitness in the form appended to these rules' (r.8(1)).
-- This Gazette copy prints NEITHER: page 6 (gazette p390) ends with r.15(6), the signature 'ABDUL RASHEED SOLANGI /
-- SECRETARY TO GOVT. OF SINDH' and the imprint 'Karachi: Printed at the Sindh Government Press 7-05-2020'.
--
-- Decision: LEAD, 17 Oct 2026, under the owner's delegation (chat, 15 Oct: "rest of the qs that ask my permission do
-- whatever is best none should be blocked"): release WITH A RECORDED SOURCE GAP -- the owner's own release-with-gap
-- pattern (documents 510, 2205, 4565): the rules release as published; the Schedule and the form are recorded as source
-- incompleteness; nothing is supplied.
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 4517 (dry run; --apply only if it is unchanged_copy)
--   2. this file (refuses unless step 1's attempt exists).
-- Idempotent: a second run inserts nothing once a record stands for 4517.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4517 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4517 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4517, 4646, 'no_complete_copy_acquired', NULL,
       'The copy ends on gazette page 390 (p6) with rule 15(6), the signature "ABDUL RASHEED SOLANGI / SECRETARY TO '
       'GOVT. OF SINDH" and the imprint "Karachi: Printed at the Sindh Government Press 7-05-2020"; no Schedule and no '
       'form follow.',
       'The Schedule to these rules (r.2(1)(h); the operations it specifies are relied on by r.1(2), 8(1), 12(1) and '
       '15(1)-(6)) and the form of the certificate of fitness "appended to these rules" (r.8(1)).',
       'Pages 2, 3 and 6 read on their renders (builder BZ, 17 Oct 2026). p2: r.1(2) "These rules shall apply to all '
       'factories in which any operation specified in the Schedule is carried on."; p3: r.2(1)(h) "\"Schedule\" means the '
       'Schedule to these rules", r.8(1) "... unless a certificate of fitness in the form appended to these rules granted '
       'to him by a certifying Surgeon is in the custody of the Manager of the factory."; p6: r.15(1)-(6) "operations '
       'mentioned in the Schedule", then the signature and the Government Press imprint dated 7-05-2020, and nothing '
       'after. No page of the copy prints a Schedule or a form.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF; no copy printing the Schedule or the form was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the Schedule or the form was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc4646-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4646-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc4646-p6.png'),
         'render_sha256', jsonb_build_array(
           '376ea1edefa71eee73463d8b9959dd1691a72d3515202510d484848904bc679e',
           '9a9040399dee1e7bce79fb836187c9aac45b96673a66f98154cff24643255cdd',
           '600017aea9754ccd3824f6c5a9818d36e0be842496e2bb4c3cbc9a7b0cd43d3f'),
         'missing_units', jsonb_build_array('the Schedule (operations)', 'the form of the certificate of fitness (r.8(1))'),
         'owner_decision', jsonb_build_object(
           'source', 'lead decision under the owner''s chat delegation (15 Oct 2026)',
           'date', '2026-10-17', 'document_id', 4646, 'choice', 'release-with-gap',
           'pattern', jsonb_build_array(510, 2205, 4565))),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4517
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4517);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4517) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4517: run tools/record_source_refetch.py '
                        '--observation 4517 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4517;
