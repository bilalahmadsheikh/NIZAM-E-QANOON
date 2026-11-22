-- Doc 11851 (SECP Unit Linked Products Fund Rules 2015, updated 5 Jul 2022), released 22 Nov 2026 with the regulator
-- notifications (D-115). Page 4: rule 7(1) prints '... set out as Annexure 2. A life insurer may ...'; the text layer
-- wraps the line after 'Annexure', and '2.' opened a false section '2' holding the rest of 7(1) and 7(2).
-- Held while re-segmented under the page-read reading in tools/evidence/annexure-wrap-2026-11-22/ and re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'a wrapped cross-reference number opened a false section; taken out of the release '
                                    'while repaired and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (11851, 'p4 ''Annexure'' / ''2.'' wrapped: a false section ''2'' holds r.7(1) second sentence and r.7(2)')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
