-- 17 Nov 2026, third PPC pass (document 4441), rule preamble_before_empty_division (DECISION-LOG D-068). The released
-- tree numbers the Preamble after Chapter I's sections 1-5 although it is printed above them; the rebuild changes
-- ordinals only (dry-run release diff, .artifacts/pb_diff_ppc.jsonl: same paths, text and contents). The batch replay
-- without a hold was rolled back whole by the release gate (TOC=1: the twins' '362N' row, D-064), as it should be.
-- Held while the replay runs and the contents reading is carried, then re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('preamble numbered after the sections printed below it'),
       '[]'::jsonb,
       jsonb_build_object('reason', 'the Preamble is ordered after sections 1-5 of Chapter I; taken out of the release '
                                    'while the tree is rebuilt with the preamble first (ordinals only) and the '
                                    'twins'' contents reading is carried',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the replay')
  FROM unnest(ARRAY[4441]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
