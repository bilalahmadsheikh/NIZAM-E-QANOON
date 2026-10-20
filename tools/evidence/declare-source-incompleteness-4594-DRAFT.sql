-- DRAFT by agent K6 (18 Oct 2026, prepare mode; not run). Applied by the lead's script
-- .artifacts/release-work-2026-09-24/claude/agK6/lead-ocr-4594.sh (step 5a, RELEASE only, before the readings are
-- recorded). Pattern: declare-source-incompleteness-4575-DRAFT.sql, -3533.sql.
--
-- Document 4594, the Sindh Prisons and Corrections Services Rules, 2019 (Home Department notification No.
-- HD/SO(PRS-1)/SP&CRS/2019 of 31 March 2020; Sindh Government Gazette, 14 May 2020, Part I, gazette pages 392-554),
-- observation 4746 (https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-21-000025.pdf,
-- SHA-256 d6fb61cd0d4fa5a7ed2da82b33a88e1ece8bed1f3ac9606dc9288bd046a711fd, 162 pages, scanned: lane E4). The row names
-- the ACTIVE OCR-PROMOTED REVISION of 4594 (same blob, so the 0054 guard accepts it), which is the revision that releases;
-- the file refuses unless that revision exists.
--
-- The copy never prints gazette page 551. PDF p159 is gazette page 550 (running head 'PART-I THE SINDH GOVT. GAZETTE
-- MAY, 14, 2020 550'): 'SCHEDULE -I (See rules 35(3), 36(2), ...) Powers to respect with all Officers' and its table, rows
-- 1 TRANSFERS/POSTING to 11 ('(1) Cash awards to Prison Officers ... (2) Members of Public for rendering assistance in
-- Service'). PDF p160 is gazette page 552 (the owner's transcription; its head line '... 552'): 'SCHEDULE-III (See rule
-- 355)', the uniform table. The folio run of PDF pp158-162 is 549|550|552|553|554. Schedule-II -- the schedule rule 2(1)(g)
-- ('Senior and Junior employee ... under Schedule-II') and 2(1)(o) ('classified as Senior and Junior Prison Officer
-- under Schedule-II') cite -- is not in this copy, nor whatever of Schedule-I continued onto page 551.
--
-- Owner decision: .artifacts/decision-review/exports/decision-review-2026-10-18-4594.json (sha256 0cbd1248...), document
-- 4594, q3 'release-with-gap' (the owner in chat, 18 Oct 2026: 'Release with gap recorded (Recommended)'). The rules
-- release as printed; nothing is supplied. Raised by agent K6 (claude/agK6/anomalies-4594.json).
--
-- Read from the renders (agent K6, 18 Oct 2026): .artifacts/ocr-review-pack-owner-2026-10-17/doc-4594/images/
--   page-159.png 72608c86... folio 550, SCHEDULE -I, its table rows 1-11 (and a show-through Gazette stamp at the foot);
--   page-160.png bc75fef2... no OCR text (the owner typed it): SCHEDULE-III, folio 552 in his head line.
--
-- ORDER (the lead script's step 5a, after the promotion, segmentation and pin, before the readings are recorded):
--   1. python tools/record_source_refetch.py --observation 4746 (dry run; --apply only if it is unchanged_copy or
--      network_error -- the gap is proven by the copy itself, the refetch only asks whether a complete copy is now
--      served, so a failed one is recorded as a dated attempt and the evidence says a refetch is owed. Never on a
--      changed copy, an http_error or an invalid PDF.)
--   2. this file (refuses unless step 1's attempt exists and the promoted revision exists).
-- Migration 0054 accepts this: its trigger checks only that the observation landed and that the document is of its
-- blob. The audit reports v_source_incompleteness_open and never fails on it.
-- Idempotent: a second run inserts nothing once a record stands for 4746.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM acquisition_attempt
                WHERE source_observation_id = 4746 AND outcome = 'recovered') THEN
        RAISE EXCEPTION 'observation 4746 has a recovered attempt: a different copy was landed. Read it first.';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM document WHERE supersedes_document_id = 4594 AND is_active) THEN
        RAISE EXCEPTION '4594 has no active promoted revision: promote it first (lead-ocr-4594.sh step 2)';
    END IF;
END $$;

INSERT INTO source_incompleteness (
    source_observation_id, document_id, resolution, complete_document_id,
    body_stops_at, promised_top, observed, attempts_considered,
    first_attempt_at, last_attempt_at, observed_error, evidence, asserted_by
)
SELECT 4746,
       (SELECT id FROM document WHERE supersedes_document_id = 4594 AND is_active ORDER BY id DESC LIMIT 1),
       'no_complete_copy_acquired', NULL,
       'PDF page 159 (gazette page 550) prints SCHEDULE -I and its table, rows 1 (TRANSFERS/POSTING) to 11 ("(1) Cash awards '
       'to Prison Officers subject to condition that reward amount is not beyond one basis pay (2) Members of Public for '
       'rendering assistance in Service"); PDF page 160 (gazette page 552) opens "SCHEDULE-III (See rule 355)". Gazette '
       'page 551 is not in the copy.',
       'Gazette page 551: Schedule-II (cited by rule 2(1)(g) and (o): the classification of Senior and Junior Prison '
       'Officers and employees), and any continuation of Schedule-I.',
       'PDF pages 158-162 read on their renders and through the owner-reviewed OCR (agent K6, 18 Oct 2026; '
       'ocr-review-doc-4594-v3.json: 159/162 accepted, pp155, 160, 161 typed by the owner). Folio run 549|550|552|553|554: '
       'p158 (549) rules 953-956 and the signature; p159 (550) SCHEDULE -I; p160-161 (552-553) SCHEDULE-III, typed by the '
       'owner; p162 (554) the AFFIRMATION ROLL and the imprint. Rules 1-956, Schedule-I as far as printed, Schedule-III and '
       'the Affirmation Roll release as printed.',
       count(*), min(attempted_at), max(attempted_at),
       CASE WHEN bool_and(outcome = 'unchanged_copy')
            THEN 'A dated refetch of the official URL returned the same 162-page PDF (SHA-256 d6fb61cd...); no copy '
                 'printing gazette page 551 was obtained.'
            WHEN NOT bool_or(outcome = 'unchanged_copy') AND bool_or(outcome = 'network_error')
            THEN 'The official URL could not be reached (dated refetch: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '). The gap rests on the copy itself (gazette folio run 550|552 on PDF pp159-160); whether a complete '
                    'copy is now served is unverified -- a refetch is owed.'
            ELSE 'Dated refetches returned: '
                 || string_agg(DISTINCT outcome || coalesce(' (' || left(error, 160) || ')', ''), '; ')
                 || '; no copy printing gazette page 551 was obtained.'
       END,
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'attempt_ids', jsonb_agg(id ORDER BY id),
         'render_artifact', jsonb_build_array(
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4594/images/page-159.png',
           '.artifacts/ocr-review-pack-owner-2026-10-17/doc-4594/images/page-160.png'),
         'render_sha256', jsonb_build_array(
           '72608c86cd062bb7962ef479a5733b7505d60f8af6edaa5593aca846923eec04',
           'bc75fef2033ed1c8496509cd59a6374abb1009c97c127a4a59eb71afd134a75b'),
         'missing', jsonb_build_array(
           jsonb_build_object('what', 'gazette page 551: Schedule-II and any continuation of Schedule-I',
                              'between', 'SCHEDULE -I row 11 (PDF p159, gazette 550) and SCHEDULE-III (PDF p160, gazette 552)')),
         'gap_proof', jsonb_build_object(
           'basis', 'the copy itself: gazette folio run 549|550|552|553|554 on PDF pp158-162; rule 2(1)(g) and (o) cite '
                    'a Schedule-II the copy does not print',
           'renders', jsonb_build_array('page-159.png', 'page-160.png')),
         'refetch', jsonb_build_object(
           'outcomes', jsonb_agg(DISTINCT outcome),
           'complete_copy_checked', bool_or(outcome = 'unchanged_copy'),
           'owed', NOT bool_or(outcome = 'unchanged_copy'),
           'note', CASE WHEN bool_or(outcome = 'unchanged_copy')
                        THEN 'the portal served the same PDF'
                        ELSE 'the portal (sindhlaws.gov.pk) could not be reached; the refetch only checks whether a '
                             'complete copy is now available, so it is owed: rerun tools/record_source_refetch.py '
                             '--observation 4746 when the portal answers, and supersede this record if it serves a '
                             'different copy'
                   END),
         'readings', '.artifacts/release-work-2026-09-24/claude/agK6/patch-<promoted id>.json (work/agK6-mk_4594.py; simulated: patch-4594-sim.json)',
         'owner_decision', jsonb_build_object(
           'source', '.artifacts/decision-review/exports/decision-review-2026-10-18-4594.json',
           'source_sha256', '0cbd1248927b94a65381ee1567a2e4293895168983faeef32051bc924eabc508',
           'date', '2026-10-18', 'document_id', 4594, 'question_id', 'q3', 'choice', 'release-with-gap',
           'pattern', jsonb_build_array(3533, 4575))),
       'claude.source-incompleteness-review/1'
  FROM acquisition_attempt
 WHERE source_observation_id = 4746
   AND outcome IN ('unchanged_copy', 'http_error', 'network_error', 'invalid_pdf')
HAVING count(*) > 0
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4746);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4746) THEN
        RAISE EXCEPTION 'no acquisition_attempt for observation 4746: run tools/record_source_refetch.py '
                        '--observation 4746 --apply first';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, document_id, resolution, attempts_considered, last_attempt_at, observed_error
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4746;
