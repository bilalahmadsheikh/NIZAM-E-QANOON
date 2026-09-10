-- Correct the verifier scopes in the quality-status view.  E3 pages may carry
-- an OCR candidate without using it; an OCR check is required only when the
-- active text actually contains confidence-labelled OCR blocks (or the whole
-- document is E4).  Sequence and plausibility checks use pdftotext and therefore
-- apply only to non-E4 documents.
BEGIN;

CREATE OR REPLACE VIEW v_document_quality_status AS
SELECT d.id AS document_id,
       d.sha256,
       d.lane,
       char_v.outcome AS character_outcome,
       ocr_v.outcome AS ocr_outcome,
       order_v.outcome AS order_outcome,
       text_v.outcome AS text_quality_outcome,
       CASE
         WHEN (d.lane <> 'E4' AND char_v.id IS NULL)
           OR (d.lane <> 'E4' AND order_v.id IS NULL)
           OR (d.lane <> 'E4' AND text_v.id IS NULL)
           OR (uses_ocr.required AND ocr_v.id IS NULL)
           THEN 'missing_evidence'
         WHEN char_v.outcome IN ('review','unverifiable')
           OR ocr_v.outcome IN ('review','unverifiable')
           OR order_v.outcome IN ('review','unverifiable')
           OR text_v.outcome IN ('review','unverifiable')
           THEN 'review'
         ELSE 'passed'
       END AS overall_outcome
  FROM document d
  CROSS JOIN LATERAL (
    SELECT d.lane = 'E4' OR EXISTS (
      SELECT 1 FROM text_block b
       WHERE b.document_id=d.id AND b.confidence IS NOT NULL
    ) AS required
  ) uses_ocr
  LEFT JOIN LATERAL (
    SELECT v.id,v.outcome FROM extraction_verification v
     WHERE v.document_id=d.id AND v.verifier LIKE 'nizam.verify_extraction/%'
     ORDER BY v.verified_at DESC,v.id DESC LIMIT 1
  ) char_v ON true
  LEFT JOIN LATERAL (
    SELECT v.id,v.outcome FROM extraction_verification v
     WHERE v.document_id=d.id AND v.verifier LIKE 'nizam.verify_ocr/%'
     ORDER BY v.verified_at DESC,v.id DESC LIMIT 1
  ) ocr_v ON true
  LEFT JOIN LATERAL (
    SELECT v.id,v.outcome FROM extraction_verification v
     WHERE v.document_id=d.id AND v.verifier LIKE 'nizam.verify_order/%'
     ORDER BY v.verified_at DESC,v.id DESC LIMIT 1
  ) order_v ON true
  LEFT JOIN LATERAL (
    SELECT v.id,v.outcome FROM extraction_verification v
     WHERE v.document_id=d.id AND v.verifier LIKE 'nizam.verify_text_quality/%'
     ORDER BY v.verified_at DESC,v.id DESC LIMIT 1
  ) text_v ON true
 WHERE d.is_active;

COMMIT;
