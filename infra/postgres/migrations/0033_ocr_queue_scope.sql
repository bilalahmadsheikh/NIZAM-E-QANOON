-- 0033  scope the OCR adjudication queue to documents actually in review
--
-- 0032's queue returned 101 rows. Only 16 documents fail Q1; the rest were
-- historical `tesseract-5.3.4` candidates left over from earlier passes on
-- documents that have since passed. A worklist that lists finished work is not
-- a worklist, and the useful rows were buried under eighty that were not.
--
-- The queue now shows a document only when the independent OCR verifier still
-- says `review`. Candidates for passed documents remain in
-- v_ocr_adjudication_evidence -- they are evidence, and evidence is not pruned
-- (C7) -- they simply stop being presented as outstanding work.
--
-- What the scoped queue shows, on the first four Urdu documents and the five
-- English ones, is why the two halves of Q1 are different problems:
--
--     4504  ur   Tesseract 0.3335 -> Surya 0.9587   gain 0.6253
--     4505  ur   Tesseract 0.3404 -> Surya 0.9593   gain 0.6189
--     4506  ur   Tesseract 0.3589 -> Surya 0.9600   gain 0.6011
--     4546  en   Tesseract 0.5757 -> ensemble 0.6460   gain 0.0703
--     4604  en   Tesseract 0.6180 -> ensemble 0.6361   gain 0.0181
--
-- A different engine on Nastaliq is worth ~0.6. More Tesseract on English is
-- worth ~0.02-0.07 and does not reach the 0.70 floor, which is the measured
-- reason the English five need Surya too rather than another ensemble pass.

BEGIN;

-- DROP then CREATE, not CREATE OR REPLACE: the column list changes, and
-- Postgres refuses to rename or reorder a view's columns in place.
DROP VIEW IF EXISTS v_ocr_adjudication_queue;

CREATE VIEW v_ocr_adjudication_queue AS
SELECT e.document_id,
       max(e.sha256)                                     AS sha256,
       max(e.language)                                   AS language,
       max(e.document_ocr_outcome)                       AS ocr_outcome,
       count(*)                                          AS candidate_pages,
       count(*) FILTER (WHERE e.decision = 'review')     AS pending_pages,
       round(avg(e.stored_confidence), 4)                AS stored_confidence,
       round(avg(e.candidate_confidence), 4)             AS candidate_confidence,
       round(avg(e.confidence_gain), 4)                  AS mean_gain,
       max(e.candidate_engine)                           AS candidate_engine,
       max(e.document_ocr_problems::text)                AS ocr_problems
  FROM v_ocr_adjudication_evidence e
 WHERE e.confidence_rank = 1
   -- only documents the verifier still holds in review: this is Q1's worklist,
   -- not the whole candidate history
   AND e.document_ocr_outcome IS DISTINCT FROM 'passed'
 GROUP BY e.document_id;

COMMENT ON VIEW v_ocr_adjudication_queue IS
    'Q1''s worklist: documents whose OCR the independent verifier still holds '
    'in review, with the best candidate per page. mean_gain says what a '
    'decision is worth; pending_pages says how much is left to decide. '
    'Candidates for already-passed documents stay in '
    'v_ocr_adjudication_evidence as evidence, but are not outstanding work.';

COMMIT;
