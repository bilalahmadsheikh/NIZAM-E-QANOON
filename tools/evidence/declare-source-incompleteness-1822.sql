--
-- Drafted by agent CK (8 Oct 2026, prepare mode); renamed without -DRAFT and run by builder BZ on 8 Oct 2026
-- after the dated refetch.
-- Pattern: tools/evidence/declare-source-incompleteness-510.sql / -1121.sql / -1247.sql.
--
-- Document 1822, ENVIRONMENTAL TRIBUNAL RULES, 1999: the landed copy prints Schedules II and III as
-- headings only.
--
-- Observation 2196, https://punjabcode.punjab.gov.pk/uploads/articles/environmental-tribunal-rules-1999-pdf.pdf,
-- SHA-256 4cef420944830b6d417107f94fa66c4ff12e1fd1838169d309b611ad83295cd4, seven pages. After the reviewed
-- split (tools/evidence/multi-instrument-plans/doc-1822.json) the observation carries three expressions; the
-- gap is in expression 0, the Environmental Tribunal Rules, 1999 (pp1-5). The two 2 June 1999 notifications
-- (expressions 1 and 2, pp5-6) are complete as printed.
--
-- Owner decision: decision-review-2026-10-08-h.json, document 1822, q2, choice "release-with-gap" (reviewer
-- Bilal Ahmad): "Retain Schedule II and Schedule III under their printed headings and cross-references, but
-- record their substantive contents as unavailable in this source copy. Rule 9(1) refers to Schedule II and
-- rule 17(2)(iii) refers to fees prescribed in Schedule III, confirming that substantive material is omitted.
-- Release the Rules with a source-incompleteness flag; do not reconstruct the missing schedules from another
-- source unless separately authorized."
--
-- Read from the renders on 2026-10-08 (agent CK): p1 (c72b33c3...) the contents lists rules 1-18 only (no
-- Schedule rows). p3 (3992bfc9...) rule 9 'Staff of the Tribunal. Staff of the Tribunal shall be as set out in
-- Schedule II.' (block 122511). p4 (d484fbf8...) rule 17(2)(iii) 'fees, as prescribed in Schedule III.' (block
-- 122530). p5 (c79db00c...) prints 'SCHEDULE 1 (See Rule 6) OATH OF CHAIRPERSON AND MEMBERS' with the oath;
-- then 'SCHEDULE II [See Rule 9(1)] STAFF OF THE TRIBUNAL' (blocks 122537-122539) followed by about a third of
-- a page of blank space; then 'SCHEDULE III [See Rule 16(2)(iii)] FEES FOR APPEALS' (blocks 122540-122542,
-- the cross-reference sic: the fees provision is rule 17(2)(iii)) followed by blank space and then the next
-- instrument, 'GOVERNMENT OF PAKISTAN / MINISTRY OF LAW, JUSTICE AND HUMAN RIGHTS [2nd June, 1999]
-- NOTIFICATION S.R.O.(1)/89 ...' (block 122543). Nothing is printed under either Schedule heading: no table, no
-- list of posts, no fee, no omission mark or footnote.
--
-- A dry run of tools/record_source_refetch.py --observation 2196 on 2026-10-08 returned HTTP 200,
-- application/pdf, 159770 bytes, SHA-256 4cef4209... = the held blob ('unchanged_copy'); it recorded nothing
-- (prepare mode).
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 2196 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal serves the same bytes, otherwise the
--      error it gave). If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first --
--      this file then refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows: the contents lists rules 1-18 only and prints no Schedule row, so no contents
--   row is left pending by the gap (the in-memory three-expression build links rows 1-18, unlinked []).
--
-- Idempotent: a second run inserts nothing once a record stands for 2196.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 2196 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 2196 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 2196, 1822, 'no_complete_copy_acquired', NULL,
       'Page 5 prints the headings "SCHEDULE II [See Rule 9(1)] STAFF OF THE TRIBUNAL" and "SCHEDULE III [See '
       'Rule 16(2)(iii)] FEES FOR APPEALS" with nothing under either; the next block is the heading of the '
       'separate 2 June 1999 notification.',
       'Rule 9 "Staff of the Tribunal shall be as set out in Schedule II." (p3) and rule 17(2)(iii) "fees, as '
       'prescribed in Schedule III." (p4): the staff of the Tribunal (Schedule II) and the fees for appeals '
       '(Schedule III).',
       'All seven rendered pages read. The contents (p1) lists rules 1-18 and no Schedule. The Rules (pp2-5) print '
       'the S.R.O.(1)/2001 notification, rules 1-18 and three Schedule headings. SCHEDULE 1 "(See Rule 6) OATH OF '
       'CHAIRPERSON AND MEMBERS" prints the oath. SCHEDULE II "[See Rule 9(1)] STAFF OF THE TRIBUNAL" is followed '
       'by blank space, SCHEDULE III "[See Rule 16(2)(iii)] FEES FOR APPEALS" (sic: the fees provision is rule '
       '17(2)(iii)) by blank space and then "GOVERNMENT OF PAKISTAN / MINISTRY OF LAW, JUSTICE AND HUMAN RIGHTS '
       '[2nd June, 1999] NOTIFICATION S.R.O.(1)/89", a separate instrument. No table, list, fee, omission mark '
       'or footnote is printed under Schedule II or III. Rule 9 and rule 17(2)(iii) refer to their contents, so '
       'substantive material is omitted from this copy (owner q2). Both Schedules are kept under their printed '
       'headings and cross-references; their contents are not reconstructed.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same seven-page PDF '
                 '(SHA-256 4cef4209...); no copy printing Schedules II and III was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing Schedules II and III was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '4cef420944830b6d417107f94fa66c4ff12e1fd1838169d309b611ad83295cd4',
         'expression_ordinal', 0,
         'expression_title', 'Environmental Tribunal Rules, 1999',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p3.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p4.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc1822-p5.png'),
         'render_sha256', jsonb_build_array(
           'c72b33c3094b6115b3c062ace516adc5a1eba7fee60e2c8002433eb3957e97d5',
           '3992bfc99d1e25ebaa8a3bba31a436bbe1f9de159addaa8757b8f52802464b94',
           'd484fbf870e214d0472025afe0c74a0ed5773da19004c96824b9b0808818ceec',
           'c79db00cd72a2007e75105bf4693cba3ad0de2bb500fd535512adf332a35bd05'),
         'missing_divisions', jsonb_build_array(
           jsonb_build_object(
             'printed_label', 'SCHEDULE II', 'printed_reference', '[See Rule 9(1)]',
             'printed_heading', 'STAFF OF THE TRIBUNAL', 'page', 5,
             'heading_source_block_ids', jsonb_build_array(122537, 122538, 122539),
             'referred_to_by', jsonb_build_array(jsonb_build_object(
               'rule', '9', 'page', 3, 'source_block_id', 122511,
               'printed', 'Staff of the Tribunal shall be as set out in Schedule II.'))),
           jsonb_build_object(
             'printed_label', 'SCHEDULE III', 'printed_reference', '[See Rule 16(2)(iii)]',
             'printed_heading', 'FEES FOR APPEALS', 'page', 5,
             'heading_source_block_ids', jsonb_build_array(122540, 122541, 122542),
             'referred_to_by', jsonb_build_array(jsonb_build_object(
               'rule', '17(2)(iii)', 'page', 4, 'source_block_id', 122530,
               'printed', 'fees, as prescribed in Schedule III.')),
             'source_anomaly', 'the printed cross-reference names rule 16(2)(iii); the fees provision is rule 17(2)(iii). Kept as printed.')),
         'missing_contents_rows', jsonb_build_array(),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-08-h.json',
           'document_id', 1822, 'question_id', 'q2',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; Schedules '
                         'II and III stand under their printed headings and cross-references with their contents '
                         'shown as not available in this copy -- never fabricated, never reconstructed from '
                         'another source without separate authorisation.',
         'recovery_path', 'retry punjabcode.punjab.gov.pk or find a Gazette of Pakistan copy of the Environmental '
                          'Tribunal Rules (S.R.O.(1)/2001) printing Schedules II and III; land it with '
                          'recover_acquisition.py --alternate-for 2196 --url <that copy>; using it needs a separate '
                          'owner authorisation (q2)'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 2196
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2196);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 2196) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 2196: run '
                        'tools/record_source_refetch.py --observation 2196 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 2196;
