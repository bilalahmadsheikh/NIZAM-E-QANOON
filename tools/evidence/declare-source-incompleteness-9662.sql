--
-- By the lead (29 Oct 2026). Pattern: declare-source-incompleteness-9681.sql.
--
-- Document 9662 (OCR revision of 5721), The Sind Rural Credit and Land Transfer Act, 1947 (Sind Act No. XLIX of 1947).
-- Observation 9889, https://sindhlaws.gov.pk/setup/Publications/PUB-14-000043.pdf,
-- SHA-256 85aea677d6de67ef9138aa76f13d5ba169283794c4bbe90f6685de36c37f69d0, nine pages (printed pp.3, 5-12).
--
-- Delegated decision: decision-review-2026-10-25-delegated.json, document 9662, q1 'release-with-gap' (owner chat
-- delegation of 25 Oct 2026; precedents 4521 q3, 9681 q1). Nothing is supplied from elsewhere.
--
-- Read from the renders (lead): p1 (e10a9f95...) is printed page 3 and ends with s.2(1)(d) '"loan" means ... under
-- the Sind Co-operative Societies Act, 1925;' (block 2618596); p2 (96493043...) is printed page 5, the typed slip of
-- the substituted section 8 ('1"8. If a debtor desires to mortgage ...', block 2618607). Printed page 4 -- the rest
-- of section 2 and sections 3 to 7 -- is not in this copy. Printed page 6 opens with the tail of the original s.8(d),
-- which the slip replaces (block 2618610, set aside).
--
-- ORDER: 1. python tools/record_source_refetch.py --observation 9889 --apply (done 29 Oct 2026: attempt 207,
-- unchanged_copy); 2. this file. No contents reading follows (the Act prints no contents).

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 9889 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 9889 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 9889, 9662, 'no_complete_copy_acquired', NULL,
       'PDF page 1 (printed page 3) ends with section 2(1)(d) "... under the Sind Co-operative Societies Act, 1925;"; '
       'PDF page 2 is printed page 5, the typed slip of the substituted section 8.',
       'Printed page 4: the remaining definitions of section 2 and sections 3, 4, 5, 6 and 7.',
       'All nine rendered pages read. Sections 1, 2(1)(a)-(d), 8-24, 24-A and 25-29 are printed (section 8 and 19 '
       'on typed slips; handwritten amendment notes set aside). The folios run 5, 6, 7, ... 12 after the title page, '
       'and no section 3-7 is printed anywhere in the copy. Released under the owner''s delegation with the '
       'missing page recorded; nothing is supplied from elsewhere.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same nine-page PDF (SHA-256 85aea677...); '
                 'no copy printing page 4 was obtained.'
            ELSE 'Dated refetches of the official URL returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing page 4 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'source_sha256', '85aea677d6de67ef9138aa76f13d5ba169283794c4bbe90f6685de36c37f69d0',
         'render_artifact', jsonb_build_array(
           '.artifacts/release-work-2026-09-24/claude/renders/doc9662-p1.png',
           '.artifacts/release-work-2026-09-24/claude/renders/doc9662-p2.png'),
         'render_sha256', jsonb_build_array(
           'e10a9f95c236090ee3c8a79e616ff8e18d1e184af343bc9c711cc9bf4bef266e',
           '96493043db690684f96785528f73b5573304ff44b2696a681d9b35a66596f8fb'),
         'missing', jsonb_build_array(jsonb_build_object(
           'what', 'printed page 4: the rest of section 2 and sections 3-7',
           'last_printed_block_id', 2618596, 'resumes_block_id', 2618607)),
         'owner_decision', jsonb_build_object(
           'export', '.artifacts/decision-review/exports/decision-review-2026-10-25-delegated.json',
           'document_id', 9662, 'question_id', 'q1', 'choice', 'release-with-gap',
           'reviewer', 'lead under owner chat delegation'),
         'recovery_path', 'find another print of Sind Act No. XLIX of 1947 (the Sind Code volume, or the Sind '
                          'Government Gazette of August 1947) and recover_acquisition.py --alternate-for 9889 --url <that copy>'),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 9889
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9889);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 9889) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 9889: run tools/record_source_refetch.py --observation 9889 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 9889;
