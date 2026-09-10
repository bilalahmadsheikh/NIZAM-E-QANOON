-- 0032  v_ocr_adjudication_evidence -- what a reviewer needs on one row
--
-- Q1 requires zero OCR documents in review, and a document only leaves review
-- when a person decides which reading of the page is correct. `page_ocr_
-- adjudication` records that decision and `v_page_ocr_candidate_review` lists
-- the candidates, but neither shows the thing the decision actually turns on:
-- the text currently IN the corpus, beside the text being proposed.
--
-- Without that, adjudication means opening the database, the candidate JSON and
-- the PDF in three places and comparing by eye. This view puts the comparison
-- on one row, with the page reference needed to check it against the source.
--
-- It decides nothing. It selects nothing as correct. Ranking is by confidence
-- so the strongest candidate is easy to find, but `decision` stays 'review'
-- until a human writes a row to page_ocr_adjudication -- which is the point of
-- S7's sibling rule: an automatic choice is a proposal, not an answer.
--
-- Measured on the first four Urdu documents, which is why this view exists:
--
--     doc 4503  Tesseract 0.348   Surya 0.9390
--     doc 4504  Tesseract 0.364   Surya 0.9635
--     doc 4505  Tesseract 0.347   Surya 0.9556
--     doc 4506  Tesseract 0.346   Surya 0.9635
--
-- Every Urdu document in the corpus is in review because Tesseract cannot read
-- Nastaliq. The candidate is not a refinement of that reading; it is a different
-- reading, and a person has to say which one the corpus keeps.

BEGIN;

CREATE VIEW v_ocr_adjudication_evidence AS
WITH stored_page AS (
    -- What the corpus holds for this page right now, in reading order, from the
    -- active extraction revision only.
    SELECT b.document_id,
           b.page_no,
           string_agg(b.text, ' ' ORDER BY b.reading_order) AS stored_text,
           avg(b.confidence)                                AS stored_confidence,
           count(*)                                         AS stored_blocks
      FROM text_block b
      JOIN document d ON d.id = b.document_id AND d.is_active
     GROUP BY b.document_id, b.page_no
),
latest_decision AS (
    SELECT DISTINCT ON (candidate_id)
           candidate_id, decision, reason, decided_by, decided_at
      FROM page_ocr_adjudication
     ORDER BY candidate_id, decided_at DESC, id DESC
),
ocr_verdict AS (
    -- Why this document is in review at all, from the independent verifier.
    SELECT DISTINCT ON (document_id)
           document_id, outcome, problems
      FROM extraction_verification
     WHERE verifier LIKE 'nizam.verify_ocr%'
     ORDER BY document_id, id DESC
)
SELECT c.id                                   AS candidate_id,
       c.document_id,
       d.sha256,                              -- open the PDF by hash
       c.page_no,
       d.language,
       d.lane,
       v.outcome                              AS document_ocr_outcome,
       v.problems                             AS document_ocr_problems,

       -- the two readings, side by side
       s.stored_text,
       c.text                                 AS candidate_text,
       round(s.stored_confidence, 4)          AS stored_confidence,
       round(c.mean_confidence, 4)            AS candidate_confidence,
       round(c.mean_confidence - s.stored_confidence, 4) AS confidence_gain,
       s.stored_blocks,
       c.word_count                           AS candidate_words,
       c.engine                               AS candidate_engine,
       c.dpi                                  AS candidate_dpi,

       -- decision state; 'review' until a person records one
       coalesce(a.decision, 'review')         AS decision,
       a.reason                               AS decision_reason,
       a.decided_by,
       a.decided_at,

       -- strongest candidate first, per page
       dense_rank() OVER (PARTITION BY c.document_id, c.page_no
                          ORDER BY c.mean_confidence DESC NULLS LAST, c.id) AS confidence_rank
  FROM page_ocr_candidate c
  JOIN document d ON d.id = c.document_id AND d.is_active
  LEFT JOIN stored_page s ON s.document_id = c.document_id AND s.page_no = c.page_no
  LEFT JOIN latest_decision a ON a.candidate_id = c.id
  LEFT JOIN ocr_verdict v ON v.document_id = c.document_id;

COMMENT ON VIEW v_ocr_adjudication_evidence IS
    'One row per OCR candidate page: the text the corpus holds now beside the '
    'text proposed, both confidences, the verifier''s reason for review, and '
    'the source hash and page to check against. Decides nothing -- decision '
    'stays ''review'' until a person writes to page_ocr_adjudication.';

-- The queue: documents whose OCR is in review and for which a stronger
-- candidate now exists. This is the worklist Q1 is waiting on.
CREATE VIEW v_ocr_adjudication_queue AS
SELECT document_id,
       max(sha256)                                       AS sha256,
       max(language)                                     AS language,
       count(*)                                          AS candidate_pages,
       count(*) FILTER (WHERE decision = 'review')        AS pending_pages,
       round(avg(stored_confidence), 4)                  AS stored_confidence,
       round(avg(candidate_confidence), 4)               AS candidate_confidence,
       round(avg(confidence_gain), 4)                    AS mean_gain,
       max(document_ocr_problems::text)                  AS ocr_problems
  FROM v_ocr_adjudication_evidence
 WHERE confidence_rank = 1
 GROUP BY document_id;

COMMENT ON VIEW v_ocr_adjudication_queue IS
    'One row per document awaiting OCR adjudication, best candidate per page. '
    'Ordered work, not a score: mean_gain says how much a decision is worth, '
    'pending_pages says how much is left to decide.';

COMMIT;
