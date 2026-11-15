-- Lift today's assistant-page-review-hold rows on OCR-lane (E4) documents once their repair is applied (15 Nov 2026).
-- The hold rows were written under nizam.verify_text_quality/2, which never runs on an E4 document (its lane is
-- verified by verify_ocr), so nothing later supersedes them. For each named E4 document whose newest verify_ocr record
-- is 'passed' AND newer than its newest hold, append the lift under the same identity: outcome passed, the repair named.
-- Documents whose OCR verification is not newer and passing are left held. __DOCS__ / __REPAIR__ filled by the caller.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d.id, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'passed', '[]'::jsonb, '[]'::jsonb,
       jsonb_build_object('reason', 'hold lifted: __REPAIR__ applied and replayed; this E4 document is verified by '
                                    'verify_ocr, whose newest record (id ' || o.id || ') passed after the replay',
                          'lifts_hold', h.id)
  FROM document d
  JOIN LATERAL (SELECT v.id, v.verified_at FROM extraction_verification v
                 WHERE v.document_id = d.id AND v.reference_extractor = 'assistant-page-review-hold'
                 ORDER BY v.verified_at DESC, v.id DESC LIMIT 1) h ON true
  JOIN LATERAL (SELECT v.id, v.outcome, v.verified_at FROM extraction_verification v
                 WHERE v.document_id = d.id AND v.verifier LIKE 'nizam.verify_ocr/%'
                 ORDER BY v.verified_at DESC, v.id DESC LIMIT 1) o ON true
 WHERE d.id = ANY(ARRAY[__DOCS__]) AND d.lane = 'E4'
   AND o.outcome = 'passed' AND o.verified_at > h.verified_at
   AND (SELECT outcome FROM extraction_verification v WHERE v.id = h.id) = 'review';
COMMIT;
