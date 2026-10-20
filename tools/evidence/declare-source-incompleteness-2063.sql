--
-- Drafted by agent CQ (10 Oct 2026, prepare mode); renamed without the draft suffix and run by builder BZ on
-- 10 Oct 2026 after the dated refetch.
-- Pattern: tools/evidence/declare-source-incompleteness-1822.sql (a gap inside one expression of a split document).
--
-- Document 2063, Sindh Development and Maintenance of Infrastructure [Cess] Rules, 1994: the landed copy prints
-- rule 12's number with no text.
--
-- Observation 4667, https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-16-000173.pdf,
-- SHA-256 34f625008b76cfeb4f88b35f4e8bfb4b397291d2eacada573787384f47fc28c2, six pages. After the reviewed split
-- (tools/evidence/multi-instrument-plans/doc-2063.json) the observation carries two expressions; the gap is in
-- expression 0, the Rules (pp1-4). The 28 June 2010 notification (expression 1, pp5-6) is complete as printed.
--
-- Owner decision: decision-review-2026-10-10-i.json, document 2063, q2, choice "release-with-gap" (reviewer Bilal
-- Ahmad, page images reviewed): "Release; record rule 12 as printed without text" -- "Rule 12 is recorded as a number
-- the copy prints with no text (source incompleteness, migration 0054); rule 12(A) is released as printed."
--
-- Read from the renders on 2026-10-10 (agent CQ): p3 (6699f8cd...) prints rules 8-11, then '12.' alone at the left
-- margin with nothing after it on its line, then, indented, '1[12 (A)  Refund of Excess Assessment.' and its text
-- '... order for the refund of such payment or over-payment.]', then '13. Recovery of dues:- ...' and '4[14(1) ...'.
-- Footnote 1 reads 'Rule 12 (a) added by Notification No.SO(Taxes) E&T/2(41)/94 Dt. 3.7.2001.' -- it accounts for
-- 12(A) only; nothing says rule 12 was omitted, repealed or substituted. No contents list exists, so no contents
-- row is left pending by the gap.
--
-- A dry run of tools/record_source_refetch.py --observation 4667 on 2026-10-10 returned HTTP 200, application/pdf,
-- 187044 bytes, SHA-256 34f62500... = the held blob ('unchanged_copy'); it recorded nothing (prepare mode).
--
-- ORDER (see migration 0060):
--   1. python tools/record_source_refetch.py --observation 4667 --apply
--      (a dated refetch of the official URL; 'unchanged_copy' if the portal serves the same bytes, otherwise the
--      error it gave). If it reports a DIFFERENT valid PDF it records nothing: land and read that copy first --
--      this file then refuses to run.
--   2. this file. It refuses unless step 1's attempt exists.
--   No contents reading follows (no contents list).
--
-- Idempotent: a second run inserts nothing once a record stands for 4667.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4667 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4667 has a recovered attempt: a different '
                        'copy was landed. Read it before declaring this one '
                        'incomplete.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4667, 2063, 'no_complete_copy_acquired', NULL,
       'Page 3 prints "12." alone, with no words, between rule 11 and the inserted "1[12 (A) Refund of Excess '
       'Assessment ...]"; the text of rule 12 is not printed anywhere in the six pages.',
       'The printed number "12." itself (p3), in the run of rules 1-14, with no omission or repeal mark.',
       'All six rendered pages read. The Rules (pp1-3) print rules 1-11, then "12." alone at the left margin, then '
       'the indented "1[12 (A) Refund of Excess Assessment. If on an application made in this behalf, ... order for '
       'the refund of such payment or over-payment.]", rule 13 and rule 14 (as substituted in 2001), and the '
       'signature; p4 is the forwarding and distribution list; pp5-6 are the separate 28 June 2010 notification. '
       'Footnote 1 on p3, "Rule 12 (a) added by Notification No.SO(Taxes) E&T/2(41)/94 Dt. 3.7.2001.", accounts for '
       '12(A) only; no footnote, stub, "[omitted]" or "[repealed]" mark accounts for rule 12. Rule 12 is held as a '
       'number with no text; nothing is reconstructed (owner q2).',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same six-page PDF '
                 '(SHA-256 34f62500...); no copy printing the text of rule 12 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing the text of rule 12 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '34f625008b76cfeb4f88b35f4e8bfb4b397291d2eacada573787384f47fc28c2',
         'expression_ordinal', 0,
         'expression_title', 'Sindh Development and Maintenance of Infrastructure [Cess] Rules, 1994',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc2063-p3.png'),
         'render_sha256', jsonb_build_array(
           '6699f8cde9503be2dd5f5db492edec956feb993f8bca3dc4fb761e20d562f50a'),
         'missing_divisions', jsonb_build_array(
           jsonb_build_object(
             'printed_label', '12', 'printed', '12.', 'page', 3, 'source_block_id', 153833,
             'note', 'the number is printed with no words; the following inserted rule 12(A) is complete and '
                     'released as printed')),
         'missing_contents_rows', jsonb_build_array(),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-10-i.json',
           'document_id', 2063, 'question_id', 'q2',
           'choice', 'release-with-gap', 'reviewer', 'Bilal Ahmad'),
         'release_note', 'Released at owner direction with a visible open source-incompleteness record; rule 12 '
                         'stands as its printed number with its text shown as not available in this copy -- never '
                         'fabricated, never recorded as omitted or repealed.',
         'recovery_path', 'retry sindhlaws.gov.pk or find a Sindh Government Gazette copy of the 22 August 1994 '
                          'notification NO:SO(TAXES) E&T/2(41)94 printing rule 12; land it with '
                          'recover_acquisition.py --alternate-for 4667 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4667
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4667);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4667) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4667: run '
                        'tools/record_source_refetch.py --observation 4667 '
                        '--apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered,
       last_attempt_at, observed_error
  FROM v_source_incompleteness_latest
 WHERE source_observation_id = 4667;
