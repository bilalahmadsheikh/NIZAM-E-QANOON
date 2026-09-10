-- 0034  the OCR queue must require a review verdict, not merely not-passed
--
-- 0033 tried to scope the queue with:
--
--     AND e.document_ocr_outcome IS DISTINCT FROM 'passed'
--
-- which is true for NULL. Most candidates belong to documents the OCR verifier
-- never examined at all -- they are not lane E4 and have no verdict -- so every
-- one of them satisfied the filter and the queue stayed at 101 rows. The intent
-- was the opposite: show a document only when a verdict EXISTS and says review.
--
-- `IS DISTINCT FROM` was reached for precisely because it handles NULL, and it
-- handled it in the wrong direction. The corrected predicate is explicit rather
-- than clever, so the NULL case is visible in the source:
--
--     AND e.document_ocr_outcome IS NOT NULL
--     AND e.document_ocr_outcome <> 'passed'

BEGIN;

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
   -- A verdict must exist and must say review. NULL means the verifier never
   -- looked at this document, which is not the same as it having a problem.
   AND e.document_ocr_outcome IS NOT NULL
   AND e.document_ocr_outcome <> 'passed'
 GROUP BY e.document_id;

COMMENT ON VIEW v_ocr_adjudication_queue IS
    'Q1''s worklist: documents whose OCR verdict exists and says review, with '
    'the best candidate per page. mean_gain says what a decision is worth; '
    'pending_pages says how much is left to decide. Candidates for passed or '
    'never-verified documents stay in v_ocr_adjudication_evidence as evidence, '
    'but are not outstanding work.';

COMMIT;
