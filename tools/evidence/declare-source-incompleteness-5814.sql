--
-- By Codex under owner delegation (3 Nov 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 5814, Khyber Pakhtunkhwa Information Technology Board Service Regulations, 2018.
-- Observation 10306, https://kpcode.kp.gov.pk/uploads/Khyber_Pakhtunkhwa_Information_Technology_Board_Service_Regulations_2018.pdf, SHA-256 f0f8037213e191d45e3d13f3b65a7ac6a543a1188a0b4c55819fb65b887892ec.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 5814, q3
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 10306 --apply (done 3 Nov 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 10306 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 10306 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 10306, 5814, 'no_complete_copy_acquired', NULL,
       'Regulation103, printed page51; no SchedulesI,IIorIII appear anywhere in the51page PDF',
       'ScheduleI(methods and qualifications),ScheduleII(post classification/pay structure),ScheduleIII(shortlisting and selection scorecards), referred to in regulations22,23,30,37,38,39and58',
       'All51page images read. The body contains103regulations and14chapters. It ends on printed page51 at regulation103, BY ORDER OF THE BOARD and Managing Director/Secretary designation, with no schedules following. Page11regulations22(3)and22(5)refer to SchedulesIIandI; page22regulation37refers to ScheduleIII; page34regulation58again refers to ScheduleII. A dated official refetch3November2026returned exactly the same51page SHA-f0f80372... PDF (acquisition_attempt212,unchanged_copy). Release the readable printed body with an explicit source limitation; supply no absent schedule text.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 f0f80372...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', 'f0f8037213e191d45e3d13f3b65a7ac6a543a1188a0b4c55819fb65b887892ec',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/z5814-11.png', '.artifacts/release-work-2026-09-24/claude/renders/z5814-22.png', '.artifacts/release-work-2026-09-24/claude/renders/z5814-34.png', '.artifacts/release-work-2026-09-24/claude/renders/z5814-51.png'),
         'render_sha256', jsonb_build_array('9b182cbfd37194fd49f23e54d61c89b116e15d306cdc78374a17c32223cdaae8', '4fc8f27a5fdb2dbb3b7eb784b4daf3a28abf6e18af6bd6b012cac2d3b69cabfb', 'c3646699bd5a524d1ac79655307c43b7e6acf90795378be20f468e5905d28bbd', '4000c8f106a2f37763c07307972e19d910fdafdfa62895b2bde953dff3cf5f60'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'ScheduleI referenced by regulation22(5), not printed in acquired PDF', 'last_printed_block_id', 1403512, 'resumes_block_id', NULL), jsonb_build_object('what', 'ScheduleII referenced by regulations22(3)and58, not printed in acquired PDF', 'last_printed_block_id', 1403831, 'resumes_block_id', NULL), jsonb_build_object('what', 'ScheduleIII referenced by regulation37, not printed in acquired PDF', 'last_printed_block_id', 1403678, 'resumes_block_id', NULL)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 5814, 'question_id', 'q3', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire an officially published complete or amended copy including the three schedules; retain this observation and declared limitation, read all recovered schedule pages and replay through the same source-audited gates. No external wording substituted.'),
       'codex.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 10306
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10306);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 10306) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 10306: run tools/record_source_refetch.py --observation 10306 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 10306;
