--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 7968, The Special Economic Zones Rules, 2013.
-- Observation 13423, https://drs.molaw.gov.pk/pdf/Special%20Economic%20Zones.pdf, SHA-256 edb95817d35ea25d261c865e27862b236da1c08693d7bf01405e00c941f77d81.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 7968, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 13423 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 13423 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 13423 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 13423, 7968, 'no_complete_copy_acquired', NULL,
       'Rule 36, PDF page 28 (printed page 24): final visible paragraph ends ''the SEZ Authority; and'' before PDF page 29 opens Chapter VII and Rule 37.',
       'The conjunction ''and'' at the end of Rule 36 promises a continuation, which this acquired source does not print.',
       'All 57 original page images read by root. Independent middle-source review confirms Rule 36''s missing continuation. PDF page 28 ends after the Developer''s land-payments paragraph and ''; and''; page 29 begins Chapter VII / Rule 37. Dated official refetch acquisition_attempt 217 on 6 November 2026 returned the identical 57-page PDF, SHA-256 edb95817d35ea25d261c865e27862b236da1c08693d7bf01405e00c941f77d81. The candidate preserves all visible wording and adds [illegible] solely at this missing tail. No missing rule text is reconstructed. The separate notification date is printed as a blank template and remains unknown.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 edb95817...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'edb95817d35ea25d261c865e27862b236da1c08693d7bf01405e00c941f77d81',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc7968-p28.png', '.artifacts/release-work-2026-09-24/claude/renders/doc7968-p29.png'),
         'render_sha256', jsonb_build_array('d06a829e47594f51741038e61ed858ad01cee202500ce87a06779e66647a3dc4', 'a0c234edf3327921a420359483944684a8e2c5bfdd295343b1360d4fa64fa798'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Unprinted continuation after Rule 36''s final visible ''; and''; no text supplied from another copy or inference.', 'last_printed_block_id', 1989910, 'resumes_block_id', 1989912)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 7968, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'If a fuller official copy is acquired, read and record its original pages under its own observation; only then replace the gap declaration. Until then retain the visible wording, explicit [illegible] marker and this declared source limitation. This is not a claim of an absent legal provision.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 13423
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13423);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 13423) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 13423: run tools/record_source_refetch.py --observation 13423 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 13423;
