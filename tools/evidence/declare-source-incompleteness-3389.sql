--
-- Drafted by agent JB (13 Oct 2026, prepare mode); the lead renames it without -DRAFT before running it.
-- Pattern: tools/evidence/declare-source-incompleteness-2146.sql (an expression of a multi-expression document).
--
-- Document 3389, observation 4610, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-17-000002.pdf,
-- SHA-256 930268ab9fe471bd536cc88a1e7fc11cb47a275e70bbc69a87b05c18ecf23cd5, 24 pages. Expression 1 (plan
-- tools/evidence/multi-instrument-plans/doc-3389-DRAFT.json): the Sindh Local Government (Local Fund Budget) Rules,
-- 2001, gazette of 5 December 2001, notification NO: SLGB/CAO/2001/7483, pp12-15 (blocks 366443-366496).
--
-- Owner decision: decision-review-2026-10-12-j.json, document 3389, q1 'release-with-gap' (reviewer Bilal Ahmad):
-- "The Budget Rules instrument covers pp12-16 (rules 1-5) only and is released with rule 6 onward and the forms
-- recorded as missing from this copy (source incompleteness). Pages 16-24 are recorded as a repeat of the
-- already-released Conduct of Business Rules and are not released again."
--
-- Read from the renders on 2026-10-13 (agent JB): p12 (c3da97ae...) the gazette head, the notification and rules 1-2
-- (definitions (a)-(g), (c) and (g) citing 'sub-rule (2) of Rule 6'); p13 (3243afde...) definitions (h)-(j), rule 3
-- 'Volume of the budget', rule 4 'Volume-I shall comprise' items a)-n) with 'Form B-1' ... ; p14 (d8f47476...) and p15
-- (c461672c...) rule 4's items to 'n. Schedule of Taxes' ('Form B-14') and rule 5 'Volume II' with the Explanatory
-- Memorandum items a.-f., ending 'f. Explanation of the Schedule of Development Expenditure: ... Section 119 of SLGO
-- 2001.'; p16 (389b5c8c...) continues with no heading into 'i. Male members shall sit in alphabetical order ...',
-- '5. Adjournment of Meeting.' ... -- the Conduct of Business Rules from rule 4(i), repeated to rule 39 on p24.
-- Rule 6 onward and Forms B-1 to B-14 are printed nowhere in the file.
--
-- A dry run of tools/record_source_refetch.py --observation 4610 on 2026-10-13 returned HTTP 200, application/pdf,
-- 344936 bytes, SHA-256 930268ab... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER:
--   1. python tools/record_source_refetch.py --observation 4610 --apply
--   2. adopt the plan (drop 3389 from PRIMARY_DOCUMENTS in tools/materialize_multi_instrument.py; rename the plan
--      without -DRAFT), record claude/agJB/patch-3389.json, materialise; E0 must rebuild identical to e31f5940.
--   3. this file (refuses until step 1's attempt exists).
--
-- Idempotent: once a record governs observation 4610 a second run inserts nothing.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4610 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4610 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4610, 3389, 'no_complete_copy_acquired', NULL,
       'The Sindh Local Government (Local Fund Budget) Rules, 2001 (expression 1): page 15 ends rule 5''s Explanatory '
       'Memorandum at item "f. Explanation of the Schedule of Development Expenditure: ... in the light of Section 119 of '
       'SLGO 2001."; page 16 continues, with no title or break, into a repeat of the Sindh Councils (Conduct of '
       'Business) Rules from rule 4(i) to rule 39 (pp16-24), which is not part of this instrument.',
       'Rule 6 onward of the Budget Rules (rule 2(c) and (g) cite "sub-rule (2) of Rule 6") and Forms B-1 to B-14, which '
       'rule 4 prescribes for the volume''s estimates, statements and schedules ("Form" means the forms appended to these '
       'Rules, rule 2(b)).',
       'Pages 12-16 read. The gazette of 5 December 2001 prints notification NO: SLGB/CAO/2001/7483 and the Budget Rules: '
       'rule 1 (short title, commencement), rule 2 (definitions (a)-(j)), rule 3 (Volume of the budget), rule 4 '
       '(Volume-I: items a)-n), each prescribing a form, B-1 to B-14) and rule 5 (Volume II and the Explanatory '
       'Memorandum, items a.-f.). After item f. the copy runs, with no heading, into "i. Male members shall sit in '
       'alphabetical order ...", "5. Adjournment of Meeting." ... "39." -- council meeting rules already released from '
       'pp1-12 of this file. No rule 6, no form and no signature of the Budget Rules is printed. The repeat is not the '
       'Budget Rules'' text and is left outside every expression (owner q1).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same twenty-four-page PDF (SHA-256 930268ab...); no '
                 'copy printing rule 6 onward or Forms B-1 to B-14 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing rule 6 onward or Forms B-1 to B-14 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '930268ab9fe471bd536cc88a1e7fc11cb47a275e70bbc69a87b05c18ecf23cd5',
         'expression_ordinal', 1,
         'expression_title', 'Sindh Local Government (Local Fund Budget) Rules, 2001',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc3389-p12.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3389-p13.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3389-p15.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc3389-p16.png'),
         'render_sha256', jsonb_build_array(
           'c3da97ae542571031d5ed4fea6ad2350a5a38f622ea4add7c5522694460fc072',
           '3243afde52f22efbac0ac866085e0e037059543ffb3adcbaf9363b614f35f1fd',
           'c461672c8c17c781d51080b155836adfa9f9c383aadf5fe9dd579a86605aec69',
           '389b5c8cb53f97654e15aab6083f4d54f41bf8e999295b9d9fd89da5cbd60742'),
         'missing_divisions', jsonb_build_array(
           jsonb_build_object('printed_label', '6 onward', 'kind', 'rule', 'page', 15,
             'last_printed_source_block_id', 366496,
             'note', 'rule 2(c) and (g) cite "sub-rule (2) of Rule 6"; no rule after 5 is printed'),
           jsonb_build_object('printed_label', 'FORMS B-1 to B-14', 'kind', 'form',
             'note', 'rule 4''s items a)-n) prescribe Forms B-1 to B-14; none is printed')),
         'repeat_outside_expressions', jsonb_build_object(
           'first_source_block_id', 366497, 'last_source_block_id', 366576, 'pages', '16-24',
           'note', 'the Conduct of Business Rules from rule 4(i) to rule 39, a repeat of expression 0 (released); not '
                   'released again (owner q1)'),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-12-j.json',
           'document_id', 3389, 'question_id', 'q1', 'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record: rule 6 onward '
                         'and the forms are shown as not available in this copy -- never as repealed, never fabricated.',
         'recovery_path', 'find a Sindh Government Gazette (5 December 2001) or Sindh Code copy of the Local Fund Budget '
                          'Rules printing rule 6 onward and the forms; then recover_acquisition.py --alternate-for 4610'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4610
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4610);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4610) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4610: run tools/record_source_refetch.py '
                        '--observation 4610 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4610;
