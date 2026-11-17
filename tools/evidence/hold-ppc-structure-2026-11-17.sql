-- 17 Nov 2026, second PPC repair pass (document 4441), after hold-ppc-footnotes-2026-11-17.sql was lifted. The released
-- tree reads the Code's opening page (CHAPTER I, INTRODUCTION, the Preamble) as contents, so the Preamble is not
-- served and Chapter I never opens; and six chapters inserted by amendment (VA, IXA, XVIA, XVIIA, XVIIB, XXA) are read
-- as the end of the section before them, their sections falling under the previous chapter. Held while the reviewed
-- body start and chapter openers (.artifacts/recrawl-queue/specs/blockfix-4441c.json) are replayed and re-verified.
-- (A replay sent before this hold was refused for the released tree by the release gate, as it should be.)
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('opening page read as contents (Preamble not served); inserted chapters read as section text'),
       '[]'::jsonb,
       jsonb_build_object('reason', 'the Preamble and Chapter I are read as contents, and six inserted chapters as the '
                                    'end of the preceding section; taken out of the release while the reviewed body '
                                    'start and chapter openers are replayed and the text re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM unnest(ARRAY[4441]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
