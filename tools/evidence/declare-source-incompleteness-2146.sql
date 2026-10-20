--
-- Drafted by agent CQ (10 Oct 2026, prepare mode); renamed without the draft suffix and run by builder BZ on
-- 10 Oct 2026 after the dated refetch.
-- Pattern: tools/evidence/declare-source-incompleteness-1822.sql (gaps inside one expression of a split document)
-- and -1247.sql.
--
-- Document 2146 (observation 4503, catalogued as 'SINDH LOCAL COUNCILS (PROPERTY) RULES, 2017'): after the reviewed
-- split (tools/evidence/multi-instrument-plans/doc-2146.json) the observation carries two expressions. The gaps are
-- in expression 1, the Sindh Councils (Budget) Rules, 2017 (pp8-32): no rule 4 is printed, and Forms B-5 to B-20 are
-- not in the file, which ends on p32 inside Form B-4. Expression 0, the Sindh Local Councils (Property) Rules, 2017
-- (pp1-7), is complete as printed.
--
-- Observation 4503, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-24-000024.pdf,
-- SHA-256 ea52d014f634a775c1e2d9c47b93e042748ec255699d3fcc2e58b89e89871988, thirty-two pages.
--
-- Owner: decision-review-2026-10-10-i.json, document 2146, q1, choice "split" (reviewer Bilal Ahmad; note: "Pages
-- 8-32 shall constitute a separate instrument titled the Sindh Councils (Budget) Rules, 2017 ... The Budget Rules and
-- their forms shall undergo separate structural verification before release"); and the owner's answers of 10 Oct
-- 2026 given to the lead (logged in CLAUDE-CLAIMS.md): verify the Budget Rules now so both instruments release
-- together, and record two source gaps -- no rule 4 is printed (p9 goes from 3(2)(n) to '5.'; rule 4 is not
-- invented), and Forms B-5 to B-20 are missing (the file ends at p32 inside Form B-4).
--
-- Read from the renders on 2026-10-10 (agent CQ), every page of the Budget Rules (pp8-32):
--   p9 (5cbbbc6d...): rule 3 '(2) Volume-I shall comprise - (a) Estimates of Revenue; ... (n) Schedule of Taxes.'
--     (block 162696) and then directly '5. Estimates of Revenue - (1) The Estimates of Receipts shall be in Form B-1
--     ...' (block 162697). No rule 4, stub, omission mark or footnote anywhere in the Budget Rules; they have no
--     contents list.
--   pp10-23: rules 8-18 prescribe Form B-4 (Financial Abstract) and Forms B-5 to B-14 (the Schedules of New
--     Expenditure ... Taxes); rule 69 Form B-15, rule 71 Form B-16, rule 76 Form B-17, rule 77 Forms B-18 and B-19,
--     rule 80(4) Form B-20; rule 2(1)(d): '"Form" means a form appended to these rules'.
--   pp26-32: Forms B-1 (pp26-29), B-2 (pp30-32), B-3 (p32) and B-4 'FINANCIAL GRANTS' (p32); p32 (efd85be4...), the
--     last page of the PDF (printed page 173), ends Form B-4 after its row '4. Total Income from taxes' (block 162999)
--     at the foot of the page. No Form B-5 to B-20 is printed.
--
-- A dry run of tools/record_source_refetch.py --observation 4503 on 2026-10-10 returned HTTP 200, application/pdf,
-- 195221 bytes, SHA-256 ea52d014... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 4503 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal serves the same bytes, otherwise the
--      error it gave). If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first --
--      this file then refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: neither instrument prints a contents list.
--
-- Idempotent: a second run inserts nothing once a record stands for 4503.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4503 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4503 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4503, 2146, 'no_complete_copy_acquired', NULL,
       'The Sindh Councils (Budget) Rules, 2017 (expression 1): page 32 of 32 ends Form B-4 "FINANCIAL GRANTS" after '
       'its row "4. Total Income from taxes"; no Form B-5 to B-20 follows. Page 9 prints rule 3 and then rule 5; no rule '
       '4 is printed.',
       'Forms B-5 to B-20, prescribed by rules 9-18, 69, 71, 76, 77 and 80 ("Form" means a form appended to these '
       'rules, r.2(1)(d)); rule 4, between rule 3(2)(n) and rule 5 (p9).',
       'All 32 rendered pages read. Pages 1-7 are the Sindh Local Councils (Property) Rules, 2017, complete as printed. '
       'Pages 8-32 are the Sindh Councils (Budget) Rules, 2017: notification of 28 February 2017, rules 1-3 and 5-84 in '
       'five chapters, the signature (p24), the forwarding and distribution list (p25), and Forms B-1 (pp26-29), B-2 '
       '(pp30-32), B-3 and B-4 (p32). On p9 rule 3(2)(n) "Schedule of Taxes." is followed directly by "5. Estimates of '
       'Revenue"; no rule 4, stub, omission mark or footnote appears and there is no contents list. Rules 8-18, 69, 71, '
       '76, 77 and 80 prescribe Forms B-4 to B-20; only Forms B-1 to B-4 are printed, and p32, the last page of the PDF '
       '(printed page 173), ends Form B-4 after its row 4 at the foot of the page. Rule 4 is not invented; the missing '
       'forms are not reconstructed (owner, 10 Oct).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same thirty-two-page PDF '
                 '(SHA-256 ea52d014...); no copy printing rule 4 or Forms B-5 to B-20 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing rule 4 or Forms B-5 to B-20 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'ea52d014f634a775c1e2d9c47b93e042748ec255699d3fcc2e58b89e89871988',
         'expression_ordinal', 1,
         'expression_title', 'Sindh Councils (Budget) Rules, 2017',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2146-p8.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2146-p9.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2146-p10.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc2146-p32.png'),
         'render_sha256', jsonb_build_array(
           'b6b356522a9d85c8fe90e4a57761ed75508ceae6adb031bb941c57da1d0a1a59',
           '5cbbbc6dc392f44b832ad90a51077ea99c644a4a157d2d940349702631832868',
           'a0154b20ad8583644bf4ed03da79bd651b7414d525d66bc31e09d157eeabc680',
           'efd85be482538bb74dbae703d02ca308226c90c4bac0da2cc1396c6e4c069786'),
         'missing_divisions', jsonb_build_array(
           jsonb_build_object(
             'printed_label', '4', 'kind', 'rule', 'page', 9,
             'between_source_block_ids', jsonb_build_array(162696, 162697),
             'note', 'rule 3(2)(n) "Schedule of Taxes." is followed directly by "5. Estimates of Revenue"; no rule 4 is '
                     'printed and none is invented'),
           jsonb_build_object(
             'printed_label', 'FORM B-4', 'kind', 'form', 'page', 32,
             'heading_source_block_ids', jsonb_build_array(162988, 162989, 162990),
             'last_printed_source_block_id', 162999,
             'note', 'printed as "FORM B-4 (See Rule 8) FINANCIAL GRANTS" (rule 8 calls it the Financial Abstract); '
                     'rows 1-4 print, and the PDF ends at the foot of p32 -- the rest of the form is not in this copy'),
           jsonb_build_object(
             'printed_label', 'FORMS B-5 to B-20', 'kind', 'form',
             'referred_to_by', jsonb_build_array(
               jsonb_build_object('rule', '9', 'form', 'B-5', 'page', 10, 'source_block_id', 162705),
               jsonb_build_object('rule', '10', 'form', 'B-6', 'page', 10, 'source_block_id', 162706),
               jsonb_build_object('rule', '11', 'form', 'B-7', 'page', 10, 'source_block_id', 162707),
               jsonb_build_object('rule', '12', 'form', 'B-8', 'page', 10, 'source_block_id', 162708),
               jsonb_build_object('rule', '13', 'form', 'B-9', 'page', 10, 'source_block_id', 162709),
               jsonb_build_object('rule', '14', 'form', 'B-10', 'page', 11, 'source_block_id', 162711),
               jsonb_build_object('rule', '15', 'form', 'B-11', 'page', 11, 'source_block_id', 162712),
               jsonb_build_object('rule', '16', 'form', 'B-12', 'page', 11, 'source_block_id', 162713),
               jsonb_build_object('rule', '17', 'form', 'B-13', 'page', 11, 'source_block_id', 162714),
               jsonb_build_object('rule', '18', 'form', 'B-14', 'page', 11, 'source_block_id', 162715),
               jsonb_build_object('rule', '69', 'form', 'B-15', 'page', 21, 'source_block_id', 162829),
               jsonb_build_object('rule', '71(1)', 'form', 'B-16', 'page', 21, 'source_block_id', 162835),
               jsonb_build_object('rule', '76(1)', 'form', 'B-17', 'page', 22, 'source_block_id', 162846),
               jsonb_build_object('rule', '77(1)', 'form', 'B-18', 'page', 22, 'source_block_id', 162848),
               jsonb_build_object('rule', '77(3)', 'form', 'B-19', 'page', 22, 'source_block_id', 162854),
               jsonb_build_object('rule', '80(4)', 'form', 'B-20', 'page', 23, 'source_block_id', 162870)),
             'note', 'r.2(1)(d): "Form" means a form appended to these rules; none of Forms B-5 to B-20 is printed')),
         'missing_contents_rows', jsonb_build_array(),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
           'document_id', 2146, 'question_id', 'q1',
           'choice', 'split', 'reviewer', 'Bilal Ahmad',
           'followup', 'owner answers of 10 Oct 2026 given to the lead, logged in CLAUDE-CLAIMS.md: record no-rule-4 '
                       'and Forms B-5 to B-20 as source gaps; release both instruments together'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; rule 4 and Forms '
                         'B-5 to B-20 (and the rest of Form B-4) are shown as not available in this copy -- never '
                         'fabricated, never recorded as omitted or repealed.',
         'recovery_path', 'retry sindhlaws.gov.pk or find a Sindh Government Gazette copy of notification '
                          'No.RO(LG)/MISC:4(74)/2016 of 28 February 2017 printing rule 4 and Forms B-5 to B-20; land '
                          'it with recover_acquisition.py --alternate-for 4503 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4503
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4503);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4503) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4503: run '
                        'tools/record_source_refetch.py --observation 4503 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 4503;
