-- Keep every OCR reading while separating evidence from promotion decisions.
-- Confidence ranks the review queue; it is never an automatic legal-text gate.
BEGIN;

CREATE TABLE page_ocr_adjudication (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    candidate_id  bigint NOT NULL REFERENCES page_ocr_candidate(id) ON DELETE RESTRICT,
    decision      text NOT NULL CHECK (decision IN ('review','accepted','rejected')),
    reason        text NOT NULL,
    evidence      jsonb NOT NULL DEFAULT '{}',
    decided_by    text NOT NULL,
    decided_at    timestamptz NOT NULL DEFAULT now(),
    CHECK (jsonb_typeof(evidence) = 'object'),
    UNIQUE (candidate_id, decision, reason)
);
CREATE INDEX page_ocr_adjudication_candidate
    ON page_ocr_adjudication(candidate_id, decided_at DESC, id DESC);

CREATE OR REPLACE VIEW v_page_ocr_candidate_review AS
WITH latest_decision AS (
    SELECT DISTINCT ON (candidate_id)
           candidate_id,decision,reason,evidence,decided_by,decided_at
      FROM page_ocr_adjudication
     ORDER BY candidate_id,decided_at DESC,id DESC
), ranked AS (
    SELECT c.*,
           coalesce(a.decision,'review') AS decision,
           a.reason AS decision_reason,
           a.evidence AS decision_evidence,
           a.decided_by,
           a.decided_at,
           p.char_count AS active_page_char_count,
           count(*) OVER (PARTITION BY c.document_id,c.page_no) AS candidate_count,
           dense_rank() OVER (
               PARTITION BY c.document_id,c.page_no
               ORDER BY (coalesce(a.decision,'review')='accepted') DESC,
                        c.mean_confidence DESC NULLS LAST,
                        c.word_count DESC,c.id
           ) AS confidence_rank
      FROM page_ocr_candidate c
      JOIN page p ON p.document_id=c.document_id AND p.page_no=c.page_no
      LEFT JOIN latest_decision a ON a.candidate_id=c.id
)
SELECT * FROM ranked;

COMMENT ON TABLE page_ocr_adjudication IS
  'Append-only reviewer decisions over retained OCR alternatives; rejecting a candidate never deletes it.';
COMMENT ON VIEW v_page_ocr_candidate_review IS
  'Ranked OCR review workbench. Rank and confidence aid triage and never authorize automatic promotion.';

COMMIT;
