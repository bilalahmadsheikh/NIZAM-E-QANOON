--
-- DRAFT by agent K4 (15 Oct 2026, prepare mode; NOT RUN). Pattern: JC's declare-source-incompleteness-3533-DRAFT.sql.
--
-- Document 3528, The West Pakistan Finance Act, 1963 (W.P. Act No. IX of 1963), KP Code copy, observation 1533
-- (canonical_url https://kpcode.kp.gov.pk/uploads/1963_9_THE_WEST_PAKISTAN_FINANCE_ACT_1963.pdf). Section 7 ('Tax on
-- callings, professions, etc.') opens on p5 ('There shall be levied and collected from the following classes of persons
-- a tax of the amount specified against each for the financial year 1963-64:--'); p6 begins with the table heads 'Class
-- of persons / Amount of tax' and item '(iv) Legal practitioners ...'. Items (i)-(iii) are printed nowhere: no stub, no
-- omission mark, no footnote (claude/agJC/card-3528-s7.json).
--
-- Owner decision: decision-review-2026-10-14-l.json, document 3528, q2 'release-with-gap' (reviewer Bilal Ahmad).
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 1533 --apply   (dated attempt; dry run first)
--   2. this file (refuses unless step 1's attempt exists).
--   No contents row names s.7's items, so no TOC reading follows. JC's
--   tools/evidence/record-reviewed-toc-omission-3528-DRAFT.sql (q1 'omitted') runs after the first replay as written.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 1533 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 1533 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 1533, 3528, 'no_complete_copy_acquired', NULL,
       'Section 7''s table jumps from its opening words (end of p5) to item (iv) (head of p6): items (i)-(iii) are not '
       'printed.',
       'Section 7 items (i)-(iii) (the first three classes of persons and their tax), before item (iv) "Legal '
       'practitioners of not less than five year standing".',
       'Pages 5 and 6 read on their renders. p5 ends with s.7 "There shall be levied and collected from the following '
       'classes of persons a tax of the amount specified against each for the financial year 1963-64:--" and its margin '
       'note; p6 begins "Class of persons / Amount of tax" and "(iv) Legal practitioners of not less than five year '
       'standing. Twenty rupees.", then (v)-(vii). No stub, omission stars or footnote stands for (i)-(iii).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF; no copy printing s.7(i)-(iii) was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing s.7(i)-(iii) was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p5.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3528-p6.png'),
         'render_sha256', jsonb_build_array(
           'a2bc9d86e5cbe6743292cbdc17232a40226d9969681900e2001f572b5857fa88',
           '26c5d14416386e398dcb738c53c0319146b7311ca3a7bb5a47fab94ff9800165'),
         'missing_units', jsonb_build_array('s.7(i)', 's.7(ii)', 's.7(iii)'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-14-l.json',
           'document_id', 3528, 'question_id', 'q2', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad')),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 1533
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 1533);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 1533) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 1533: run tools/record_source_refetch.py '
                        '--observation 1533 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 1533;
