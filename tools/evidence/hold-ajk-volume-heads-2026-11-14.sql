-- AJK landing 14 Nov 2026: in 344 released AJK documents the code volume's running head printed at the top of a page
-- ('407 Volume VII (1981 to 1984)', 'VOLUME IV: 1974-1977', 'AJ&K Revised Volume') was read into a provision as body
-- text -- one block per document, the block's whole text. Found by the volume-head census (block text matches the
-- volume pattern, top 0.15 of the page, assigned 'body' in provision_block); pages read for each volume's head shape
-- (docs 9917, 9918, 9921, 9948, 10182 p2). Held while each head block is set aside (patch-DOCh.json, rule
-- reviewed_apparatus_block, no law text edited), then re-verified and released. __DOCS__ is filled by the apply script.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('the code volume''s page running head read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'the AJK code volume''s running head read into released provision text; taken out '
                                    'of the release while the head block is set aside and the text re-verified',
                          'reverify', 'verify_text_quality is re-run after the repair')
  FROM unnest(ARRAY[__DOCS__]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
