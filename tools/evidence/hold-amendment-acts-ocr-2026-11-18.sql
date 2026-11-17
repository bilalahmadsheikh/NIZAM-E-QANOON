-- 18 Nov 2026, DECISION-LOG D-076. The 25th, 26th and 27th Constitution Amendment Acts (docs 11385, 11384, 11383),
-- landed from the National Assembly's gazetted copies. Their text layer is a scan's poor OCR (Article 9A read as
-- '94', the 25th's seat table misread), so they are held while each page is read on Kaggle (Qwen3-VL-8B and Surya),
-- proofread against the page image and recorded as page readings; then the verifier chain is re-run.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('scan text layer is poor OCR; held for page-read transcription'),
       '[]'::jsonb,
       jsonb_build_object('reason', 'the embedded OCR misreads article numbers and figures; every page is read on a '
                                    'GPU (vision model + Surya), proofread against its image and recorded as a page '
                                    'reading before release',
                          'reverify', 'verify_extraction, verify_order and verify_text_quality are re-run after the readings')
  FROM unnest(ARRAY[11383, 11384, 11385]) AS h(d)
 WHERE NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at >= (SELECT max(v.verified_at) FROM extraction_verification v
                                             WHERE v.document_id = h.d));
COMMIT;
