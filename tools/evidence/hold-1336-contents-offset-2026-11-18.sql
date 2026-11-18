-- Doc 1336, the Sindh Cultural Heritage (Preservation) Act, 1994: its printed contents runs one row behind its body
-- from row 7 (the body prints a bare '7.' after s.6(1)), and the released tree links the rows by number, so every
-- section from s.8 carries the heading of the section before it (s.19, the penalty, headed 'Overriding effect'), and
-- the margin notes of ss.9-20 were read into the close of the section above. Found 18 Nov 2026 while pairing the
-- Heritage tab's questions with Sindh's own law (D-078). Held while it is re-segmented under the reviewed contents
-- alignment (.artifacts/heritage-2026-11-18/patch-1336.json) and re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'contents linked one row off from s.8 and margin notes read into provision text; '
                                    'taken out of the release while repaired and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (1336, 'headings of ss.8-22 taken from the contents row of the same number, which names the section '
                      'after it; margin notes of ss.9-20 read into the text of ss.8-19')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
