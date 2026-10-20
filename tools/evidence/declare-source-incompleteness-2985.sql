--
-- Drafted by agent JB (13 Oct 2026, prepare mode); renamed and applied by builder BZ on 14 Oct 2026 after the dated refetch (attempt 160).
-- Pattern: tools/evidence/declare-source-incompleteness-2146.sql; twin of declare-source-incompleteness-3389-DRAFT.sql.
--
-- Document 2985, observation 4599, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-17-000004.pdf,
-- SHA-256 c15f5a5673a5c56580bfb094ff4a5514296adea363cbdf0d02f36ed98b5f4f05, 13 pages. Expression 0 (plan
-- tools/evidence/multi-instrument-plans/doc-2985-DRAFT.json): the Sindh Local Government (Local Fund Budget) Rules,
-- 2001, gazette of 5 December 2001, notification NO: SLGB/CAO/2001/7483, pp1-4 (blocks 286898-286965).
--
-- Owner decision: decision-review-2026-10-12-j.json, document 2985, q1 'release-with-gap' (reviewer Bilal Ahmad):
-- "Only pp1-4 (rules 1-5) are released as the Local Fund Budget Rules; the rest of those rules (rule 6 onward, forms
-- B-1 to B-14) are recorded as missing from this copy (source incompleteness). The council meeting rules fragment
-- (rule 4(i) to 39, pp4-13) is flagged as part of another instrument and not released here."
--
-- Read from the renders on 2026-10-13 (agent JB): p1 (e11a885f...) gazette head, notification, rules 1-2; p2
-- (c3ee50c2...) and p3 (c7443397...) rules 3-4 (items a)-n), Forms B-1 to B-14 prescribed); p4 (8d870e51...) rule 5,
-- Explanatory Memorandum a.-f. ending '... in the light of Section 119 of SLGO 2001.', then with no heading
-- 'i. Male members shall sit in alphabetical order ...' -- the Conduct of Business Rules from rule 4(i), which run to
-- rule 39 on p13 (the instrument released as document 3389 expression 0).
--
-- A dry run of tools/record_source_refetch.py --observation 4599 on 2026-10-13 returned HTTP 200, application/pdf,
-- 284259 bytes, SHA-256 c15f5a56... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 4599 --apply
--   2. admit 'other-copy' to OWNER_CITED_LABEL_CHOICES (q2), adopt the plan (rename without -DRAFT), record
--      claude/agJB/patch-2985.json, materialise.
--   3. this file (refuses until step 1's attempt exists).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4599 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4599 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4599, 2985, 'no_complete_copy_acquired', NULL,
       'The Sindh Local Government (Local Fund Budget) Rules, 2001 (expression 0): page 4 ends rule 5''s Explanatory '
       'Memorandum at item "f. Explanation of the Schedule of Development Expenditure: ... in the light of Section 119 of '
       'SLGO 2001."; the same page continues, with no title or break, into the Sindh Councils (Conduct of Business) Rules '
       'from rule 4(i) to rule 39 (pp4-13), another instrument.',
       'Rule 6 onward of the Budget Rules (rule 2(c) and (g) cite "sub-rule (2) of Rule 6") and Forms B-1 to B-14, which '
       'rule 4 prescribes ("Form" means the forms appended to these Rules, rule 2(b)).',
       'Pages 1-5 and 13 read. The gazette of 5 December 2001 prints notification NO: SLGB/CAO/2001/7483 and the Budget '
       'Rules: rule 1 (short title, commencement), the definitions rule (printed "1.", cited 2 per owner q2), rule 3, rule 4 '
       '(Volume-I: items a)-n), each prescribing a form, B-1 to B-14) and rule 5 (Volume II and the Explanatory '
       'Memorandum, items a.-f.). After item f. the copy runs, with no heading, into "i. Male members shall sit in '
       'alphabetical order ...", "5. Adjournment of Meeting." ... "39." on p13 -- council meeting rules, the instrument '
       'released as document 3389''s first expression. No rule 6, no form and no signature of the Budget Rules is '
       'printed. The fragment is left outside every expression (owner q1).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same thirteen-page PDF (SHA-256 c15f5a56...); no '
                 'copy printing rule 6 onward or Forms B-1 to B-14 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing rule 6 onward or Forms B-1 to B-14 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'c15f5a5673a5c56580bfb094ff4a5514296adea363cbdf0d02f36ed98b5f4f05',
         'expression_ordinal', 0,
         'expression_title', 'Sindh Local Government (Local Fund Budget) Rules, 2001',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2985-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2985-p2.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2985-p4.png'),
         'render_sha256', jsonb_build_array(
           'e11a885f8b01d48b75c75ab3445a0b4037e6ff3e977987070c8c82be84dde13b',
           'c3ee50c2b5f8e3cf846a88d93acb2928be7be03a816a05a61f7cca0127787d1f',
           '8d870e51f099db391c7b18cb2b5bf6d680d85090746ac988485a752f6698dda1'),
         'missing_divisions', jsonb_build_array(
           jsonb_build_object('printed_label', '6 onward', 'kind', 'rule', 'page', 4,
             'last_printed_source_block_id', 286965,
             'note', 'rule 2(c) and (g) cite "sub-rule (2) of Rule 6"; no rule after 5 is printed'),
           jsonb_build_object('printed_label', 'FORMS B-1 to B-14', 'kind', 'form',
             'note', 'rule 4''s items a)-n) prescribe Forms B-1 to B-14; none is printed')),
         'other_instrument_outside_expressions', jsonb_build_object(
           'first_source_block_id', 286966, 'last_source_block_id', 287054, 'pages', '4-13',
           'note', 'the Sindh Councils (Conduct of Business) Rules from rule 4(i) to rule 39 -- released as document 3389 '
                   'expression 0; not released here (owner q1)'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 2985, 'question_id', 'q1', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record: rule 6 onward '
                         'and the forms are shown as not available in this copy -- never as repealed, never fabricated.',
         'recovery_path', 'find a Sindh Government Gazette (5 December 2001) or Sindh Code copy of the Local Fund Budget '
                          'Rules printing rule 6 onward and the forms; then recover_acquisition.py --alternate-for 4599'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4599
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4599);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4599) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4599: run tools/record_source_refetch.py '
                        '--observation 4599 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4599;
