--
-- By the lead (30 Oct 2026). Pattern: declare-source-incompleteness-9662.sql. Written by tools/recrawl/declare_incomplete.py.
--
-- Document 5054, The Balochistan Prisons and Prisoner's Correctional Service Act, 2026.
-- Observation 9605, http://balochistancode.gob.pk/lawdir/0f632682-2e8b-4cf7-b4fb-a6bce91a758e.pdf, SHA-256 206d94babd933f84abc2c8a85af989f1dcda249f9abae0905b4263eb0545d845.
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 5054, q1
-- 'release-with-gap' (owner chat delegation of 25 Oct 2026; owner instruction 30 Oct 'release further and if needed add
-- source incomplete'). Nothing is supplied from elsewhere.
--
-- ORDER: 1. tools/record_source_refetch.py --observation 9605 --apply (done 30 Oct 2026); 2. this file; 3. the
-- page-read records; 4. the contents gaps closed as source_incomplete (tools/adjudicate_toc_from_source.py).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 9605 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 9605 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 9605, 5054, 'no_complete_copy_acquired', NULL,
       'Scan page 78 ends with section 61(6) (Use of Restraints: ''together with the reasons, circumstances, and any Medical report relating to the incident.''); the next scan page, 79, opens with the heading ''CHAPTER-XIII OFFENCES RELATING TO ESCAPE AND PROHIBITED ACTS'' and section 75. The landed copy prints nothing between section 61 and section 75.',
       'The contents promise sections 62 (Use of Firearms), 63 (Special Protection for Vulnerable Prisoners), 64 (Reporting and Independent Inquiry), 65 (Training of Prison Officers), 66 (Prison Offences), 67 (Classification of Prisons Offences), 68 (Punishments for Prison Offences), 69 (Appeals), 70 (Publication of Offences and Penalties), 71 (Inquiry and Punishments), 72 (Procedure for Conducting Enquiries), 73 (Safeguards and Oversight) and 74 (Security and Welfare of Prison Staff), which fall between sections 61 and 75, with the chapter heading that precedes them.',
       'Both scan pages were read on their renders: page 78 closes section 61 and page 79 opens Chapter XIII at section 75, so the PDF omits the pages that would carry sections 62 to 74. The text layer of the landed copy is digital and complete for the pages it holds. A dated refetch of the official URL (acquisition_attempt 222, 7 November 2026) returned the identical PDF (SHA-256 206d94ba...). Nothing was supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same PDF (SHA-256 206d94ba...); no complete copy was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no complete copy was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '206d94babd933f84abc2c8a85af989f1dcda249f9abae0905b4263eb0545d845',
         'render_artifact', jsonb_build_array('.artifacts/release-work-2026-09-24/claude/renders/doc5054-p78.png', '.artifacts/release-work-2026-09-24/claude/renders/doc5054-p79.png'),
         'render_sha256', jsonb_build_array('854d5b789bf03d9a92f1a768fb2cb1195911ee29a641624ab6776a4d303be348', 'b81a3dc24e11240cf3838ff1d0fd9e38b34eb9509fbfa54fda678b825a480f1e'),
         'missing', jsonb_build_array(jsonb_build_object('what', 'Sections 62 to 74 (and the chapter heading above them): promised by the contents, not printed between section 61 and section 75 in the landed copy.', 'last_printed_block_id', 1025257, 'resumes_block_id', 1025258)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 5054, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'Acquire a complete copy of the Balochistan Prisons and Prisoner''s Correctional Service Act, 2026 (the balochistancode.gob.pk copy omits the pages between section 61 and section 75); read it before adding sections 62-74. Preserve this source and declaration; no external wording used in this release.'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 9605
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9605);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9605) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 9605: run tools/record_source_refetch.py --observation 9605 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 9605;
