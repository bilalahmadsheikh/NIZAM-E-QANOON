-- Recrawl 14 Nov 2026: four newly released Sindh Code texts carry their page running heads in provision text
-- ('3 THE BARRETT HODGSON INTERNATIONAL UNIVERSITY AT KARACHI (AMENDMENT), ACT 2016 SINDH ACT NO. IX OF 2018' closing
-- s.4(f) of 9905; 19 provisions of 9910). tools/recrawl/leakscan.py's head pattern knows Gazette heads only. Held while
-- the 52 head blocks are set aside (patch -r, rule reviewed_apparatus_block), then re-verified and released.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('page running heads read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'page running heads read into released provision text; taken out of the release '
                                    'while the head blocks are set aside and the text re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM unnest(ARRAY[9905, 9907, 9908, 9910]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
