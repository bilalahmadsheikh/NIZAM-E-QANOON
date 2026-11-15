-- The Sindh Code's running head -- the law's citation 'SINDH ACT NO. VI OF 1994' printed at the head of every page --
-- read into released provisions of ~230 older Sindh documents (203 blocks of their own in 189 documents, and ~50 heads
-- fused at the top of a law block; tools/recrawl/sindh_head_patch.py, 15 Nov 2026). Held while each is set aside or
-- cut (patch-DOCr.json, rule reviewed_apparatus_block; no law text edited), then re-verified and released. __DOCS__ is
-- filled by the apply script.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('Sindh Code running head read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'the running head (the law''s citation at the head of each page) read into released '
                                    'provision text; taken out of the release while it is set aside and the text '
                                    're-verified',
                          'reverify', 'verify_text_quality is re-run after the repair')
  FROM unnest(ARRAY[__DOCS__]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
