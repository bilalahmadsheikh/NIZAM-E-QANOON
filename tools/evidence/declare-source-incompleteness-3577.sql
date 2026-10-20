--
-- DRAFT by agent K4 (15 Oct 2026, prepare mode; NOT RUN). Pattern: JC's declare-source-incompleteness-3533-DRAFT.sql.
--
-- Document 3577, THE NATIONAL UNIVERSITY OF MANAGEMENT, COMPUTER SCIENCE AND TECHNOLOGY ACT, 1999 (Sindh Act No. V of
-- 2005), Sindh Code copy, observation 3047 (canonical_url https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000443.pdf).
-- THE FIRST STATUTES (pp19-24) print statute 1 ('Faculties', its list (a)-(t), p19-20) and then, with no number or margin
-- name, only '(3) The Dean shall present candidates ...' and '(4) The Dean shall exercise such powers ...' before statute 4
-- ('Teaching Department.', p20). Statute 2 and statute 3's number, name and sub-sections (1)-(2) are printed nowhere.
--
-- Owner decision: decision-review-2026-10-14-l.json, document 3577, q3 'release-with-gap' (reviewer Bilal Ahmad):
-- statutes 1 and 4-9 release with their printed numbers; the unnumbered '(3)'-'(4)' Dean lines stay as printed inside
-- statute 1; statute 2 and statute 3(1)-(2) are recorded as source incompleteness; nothing is supplied.
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 3047 --apply   (dated attempt; dry run first)
--   2. this file (refuses unless step 1's attempt exists).
--   No contents row names statutes 2-3 (the contents lists rows 39-45 = statutes 1, 4-9 only), so no TOC reading follows.
--
-- Idempotent: a second run inserts nothing once a record stands for 3047.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 3047 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 3047 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 3047, 3577, 'no_complete_copy_acquired', NULL,
       'The First Statutes break after statute 1 (p20): the next lines are an unnumbered "(3) The Dean shall present '
       'candidates ..." and "(4) The Dean shall exercise such powers ...", then statute 4; statute 2 and statute 3''s '
       'number, name and sub-sections (1)-(2) are not printed.',
       'Statute 2 and statute 3(1)-(2) of THE FIRST STATUTES (SEE SECTION 34): the printed statutes run 1, (3)-(4) '
       'unnumbered, 4, 5, 6, 7, 8, 9.',
       'Pages 19, 20, 21-24 read on their renders. Statute 1 "The University shall have the following Faculties." (margin '
       '"Faculties") with (a)-(t) ends p20 at "(t) Faculty of Languages & Culture."; the page then prints, with no '
       'statute number or margin name, "(3) The Dean shall present candidates for admission to degrees ..." and "(4) The '
       'Dean shall exercise such powers and perform such duties as may be prescribed.", then "4. (1) There shall be a '
       'teaching department ..." (margin "Teaching Department."). No stub, omission mark or footnote marks the gap. The '
       'contents (p2) lists the statutes only as rows 39-45 (Faculties, Teaching Department, ... Discipline Committee).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF; no copy printing statutes 2-3 was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing statutes 2-3 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3577-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3577-p19.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3577-p20.png'),
         'render_sha256', jsonb_build_array(
           '4498d08eb00f505f7adc90c9302515411b1e9c713b60ea4fb3b96db9bfa7d905',
           '1787a24e2dcd786a7f445f39b0294f1f9146ddee94a4de678ebd1d21521c4812',
           'c5c68be28736755fe5fb4b8d075151498ed55203382071555afcb3b6417ba0b5'),
         'missing_units', jsonb_build_array('First Statutes statute 2', 'First Statutes statute 3(1)', 'First Statutes statute 3(2)'),
         'stray_lines_kept', 'the unnumbered (3)-(4) Dean lines (block 416359, p20) stay as printed under statute 1',
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-14-l.json',
           'document_id', 3577, 'question_id', 'q3', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad')),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 3047
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 3047);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 3047) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 3047: run tools/record_source_refetch.py '
                        '--observation 3047 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 3047;
