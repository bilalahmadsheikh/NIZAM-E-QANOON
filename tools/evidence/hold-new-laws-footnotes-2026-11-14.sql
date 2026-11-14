-- Recrawl 14 Nov 2026: nine newly released Punjab/Balochistan code texts carry a page footnote in provision text
-- ('1This Act was passed by Provincial Assembly of the Punjab on 30 June 2026; and was assented ...', closing s.1 or
-- a later section). 13 blocks, found by their opening words and role 'body'. Held while they are set aside (patch -f,
-- rule reviewed_apparatus_block), then re-verified and released.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('page footnotes read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'page footnotes read into released provision text; taken out of the release while '
                                    'the footnote blocks are set aside and the text re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM unnest(ARRAY[9894, 9896, 9897, 9898, 9900, 9902, 9903, 9904]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
