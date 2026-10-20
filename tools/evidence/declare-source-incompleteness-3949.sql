-- Drafted by agent JF (17 Oct 2026); copied and applied by the owner-run batch. Pattern: declare-source-incompleteness-4646.sql (builder BZ).
--
-- Document 3949, the Punjab Code copy that binds five Punjab Education Foundation instruments (observation 2876,
-- source pk-punjab, canonical_url https://punjabcode.punjab.gov.pk/uploads/articles/punjab-edu..., SHA-256 8dcdd835...).
-- Expression 3, THE PUNJAB EDUCATION FOUNDATION SERVICE RULES 2006 (pp16-23), ends with its SCHEDULE of posts
-- (pp18-23, columns Name of the Department | Functional Unit | Name of the post | Appointing Authority | Minimum
-- Qualifications | Method of Recruitment | Age Min. | Max. | Examination, Training and other Conditions). Page 23 (the
-- last page of the Schedule in this copy) prints row 12 '12. Monitoring & Evaluation Assistants', whose Qualifications
-- cell breaks off mid-sentence at '... education sectors reforms programs. Knowledge of current monitoring and'; the
-- next page, p24, opens a different instrument, 'THE PUNJAB EDUCATION FOUNDATION REGULATIONS 2006'. The rest of row 12
-- and any rows after it are not printed anywhere in the copy.
--
-- Owner decision: .artifacts/decision-review/exports/decision-review-2026-10-17-3949.json, document 3949,
-- q4 'release-with-gap' (answered directly in chat, 17 Oct 2026; recorded by the lead): the Service Rules
-- release with the Schedule as printed (rows 1-12, row 12 as far as it is printed); the remainder of row 12 and any
-- later rows are recorded as source incompleteness; nothing is supplied.
--
-- Read on the render (agent JF, 17 Oct): .artifacts/release-work-2026-09-24/claude/renders/doc3949-p23.png
-- (350225c2...): row 11's continuation, then row 12 with its cells (Education Department | Punjab Education Foundation
-- | 12. Monitoring & Evaluation Assistants | Board of Directors | 'Graduation at least ... division ... Knowledge of
-- current monitoring and' | On Contract Basis through Selection Committee Duly Constituted by Board of Directors | 25 |
-- 40), and nothing below; p24 (8bb11175...) opens the Regulations 2006.
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 2876 (dry run; --apply only if it is unchanged_copy)
--   2. this file (refuses unless step 1's attempt exists).
-- Idempotent: a second run inserts nothing once a record stands for 2876.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 2876 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 2876 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2876, 3949, 'no_complete_copy_acquired', NULL,
       'The Service Rules 2006 (expression 3) end on p23 inside SCHEDULE row 12: its Qualifications cell breaks off at '
       '"Knowledge of current monitoring and"; p24 opens THE PUNJAB EDUCATION FOUNDATION REGULATIONS 2006.',
       'The rest of Schedule row 12 ("12. Monitoring & Evaluation Assistants") and any Schedule rows after it.',
       'Page 23 read on its render (agent JF, 17 Oct 2026). It prints row 11''s continuation ("Officer Cluster Based '
       'Training in Public Private Partnership" and the end of its qualification) and row 12: Education Department | '
       'Punjab Education Foundation | "12. Monitoring & Evaluation Assistants" | Board of Directors | "Graduation at '
       'least [ordinal printed as a superscript] division from a recognized university with the subjects like social sciences, Economics, '
       'Management, Econometrics, Statistics or other related subjects with 3 years experience of monitoring & '
       'evaluation in a national level organization. The candidate should be able to develop log frame metrics and '
       'must be familiar with the latest monitoring and evaluation techniques applied to evaluate social sector '
       'development, human development programs and education sectors reforms programs. Knowledge of current '
       'monitoring and" | On Contract Basis through Selection Committee Duly Constituted by Board of Directors | 25 | '
       '40, and nothing below it. Page 24 opens the next instrument, the Regulations 2006, with its title.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF; no copy printing the rest of the Schedule was obtained.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the rest of the Schedule was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'expression_ordinal', 3,
         'expression_title', 'The Punjab Education Foundation Service Rules 2006',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p23.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3949-p24.png'),
         'render_sha256', jsonb_build_array(
           '350225c2e530ccc7283982614723e21100a8fd75ed347f44ce4e30b4362a9a63',
           '8bb11175202f8db0a66825e942e55a43560a846161c32f239cd93dcd2d2d7d2a'),
         'last_printed_block_id', 530683,
         'missing_units', jsonb_build_array('the rest of Schedule row 12 (Monitoring & Evaluation Assistants)',
                                            'any Schedule rows after row 12'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-17-3949.json',
           'document_id', 3949, 'question_id', 'q4', 'choice', 'release-with-gap',
           'source', 'chat-direct')),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 2876
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 2876);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 2876) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 2876: run tools/record_source_refetch.py '
                        '--observation 2876 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 2876;
