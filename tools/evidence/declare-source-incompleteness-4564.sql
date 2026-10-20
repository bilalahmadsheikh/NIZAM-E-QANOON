-- Lead, 20 Oct 2026. Pattern: declare-source-incompleteness-4612-DRAFT.sql (superseded_by_complete_copy, the complete
-- copy already in the corpus and released). Applied by .artifacts/release-work-2026-09-24/claude/lead-4564-superseded.sh.
--
-- Document 4564, observation 4554 (https://sindhlaws.gov.pk/setup/publications_SindhCode/PUB-NEW-22-000008.pdf), catalogued
-- 'WORKERS COMPENSATION RULES, 2020': a scan of the Sindh Government Gazette of Thursday 20 May 2021 (No. 20) carrying the
-- Sindh Workers' Compensation Rules, 2020. It is the same print as document 4694 (document 4483's promoted revision,
-- released, instrument c785a60c) LESS THE ISSUE'S COVER PAGE: 4694 p1 is the Gazette cover ('Registered No. M. 324 ...
-- KARACHI THURSDAY MAY 20, 2021 No. 20'); 4564 opens at 4694 p2, and 4564 pN = 4694 pN+1 for N = 1-36 (the lead compared
-- the two documents' page texts page by page, 20 Oct 2026). Nothing of the Rules is missing from 4564; it is the less
-- complete copy, and the corpus releases one copy only.
--
-- Owner: decision-review-2026-10-16-m.json 4564 q1 'one-instrument' (release one copy), and in chat on 20 Oct 2026
-- (decision-review-2026-10-20-4564.json q2 'superseded-by-4694'): "if it is identical mark it as copy". Nothing new is
-- released; 4564's blocks and tree stay. tools/apply_source_incompleteness.py then sets 4564's active instrument
-- duplicate_of 4694's. No refetch: the complete copy is held. Idempotent.

\set ON_ERROR_STOP on
BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM document WHERE id = 4564 AND is_active) THEN
        RAISE EXCEPTION 'document 4564 is not active';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM instrument i JOIN v_release_instrument r ON r.id = i.id
                    WHERE i.document_id = 4694 AND i.is_active AND i.duplicate_of IS NULL) THEN
        RAISE EXCEPTION 'document 4694 has no released canonical instrument: refusing to supersede 4564 by nothing';
    END IF;
END $$;

INSERT INTO source_incompleteness
    (source_observation_id, document_id, resolution, complete_document_id,
     body_stops_at, promised_top, observed,
     attempts_considered, first_attempt_at, last_attempt_at, observed_error,
     evidence, asserted_by)
SELECT 4554, 4564, 'superseded_by_complete_copy', 4694,
       'the file opens at the Gazette issue''s second page; the issue''s cover page (4694 p1) is not in this file',
       'the Gazette cover page of 20 May 2021 (No. 20); the complete issue, cover included, is held in document 4694',
       'Page texts of 4564 (36 pages) and 4694 (37 pages) compared page by page: 4564 pN prints 4694 pN+1 for N = 1-36. '
       '4694 p1 is the cover: Registered No. M. 324, THE SINDH GOVERNMENT GAZETTE, KARACHI THURSDAY MAY 20, 2021, No. 20.',
       1,
       coalesce(o.fetched_at, o.ingested_at), coalesce(o.fetched_at, o.ingested_at),
       'no refetch: the complete copy of this Gazette issue is already in the corpus (document 4694, released)',
       jsonb_build_object(
         'reviewer_type', 'assistant',
         'review_method', 'both documents'' page texts compared page by page (4564 tesseract text layer; 4694 the '
                          'promoted Surya text of document 4483): same print, offset by one page, 4564 lacking the cover',
         'attempt_ids', '[]'::jsonb,
         'note', 'the complete copy was already in the corpus under another observation on the same portal; no new '
                 'acquisition was needed',
         'complete_document_id', 4694,
         'complete_instrument', 'c785a60c-cb7b-4fd3-b212-fa5b6b966c5e',
         'truncated_sha256', (SELECT sha256 FROM document WHERE id = 4564),
         'complete_sha256', (SELECT sha256 FROM document WHERE id = 4694),
         'sha256_note', 'two scans of one Gazette issue differ byte-wise; the page comparison settles identity',
         'page_alignment', '4564 pN = 4694 pN+1, N = 1-36; 4694 p1 (cover) absent from 4564',
         'missing', jsonb_build_array(jsonb_build_object('what', 'the Gazette issue''s cover page',
                                                         'between', 'before 4564 p1')),
         'owner_decision', jsonb_build_object(
           'source', '.artifacts/decision-review/exports/decision-review-2026-10-20-4564.json',
           'document_id', 4564, 'question_id', 'q2', 'choice', 'superseded-by-4694',
           'earlier', '.artifacts/decision-review/exports/decision-review-2026-10-16-m.json 4564 q1 one-instrument'),
         'recovery_path', 'already held: the Rules are released from document 4694; nothing further is expected'),
       'claude.source-incompleteness-review/1'
  FROM source_observation o
 WHERE o.id = 4554
   AND NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest WHERE source_observation_id = 4554);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM v_source_incompleteness_latest
                    WHERE source_observation_id = 4554 AND resolution = 'superseded_by_complete_copy'
                      AND document_id = 4564 AND complete_document_id = 4694) THEN
        RAISE EXCEPTION 'no superseded_by_complete_copy record 4564 -> 4694 for observation 4554';
    END IF;
END $$;

COMMIT;

SELECT id AS source_incompleteness_id, document_id, resolution, complete_document_id, attempts_considered
  FROM v_source_incompleteness_latest WHERE source_observation_id = 4554;
