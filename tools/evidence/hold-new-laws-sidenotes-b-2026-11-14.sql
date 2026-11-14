-- Second pass of tools/evidence/hold-new-laws-sidenotes-2026-11-14.sql: after patch -s, leakscan still found side notes
-- in 9898 (ss.13, 26), 9907 (s.12) and 9910 (ss.18, 18-B, 18-G) -- a note block whose text runs past its contents row,
-- or a note at the head of the block that opens the next section. Held again for patch -t, then re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'margin side notes read into released provision text (second pass); taken out of '
                                    'the release while repaired and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (9898, 'side notes of ss.13 and 27 read into the text of ss.13 and 26'),
               (9907, 'side note of s.12 read into the close of s.12'),
               (9910, 'side notes of ss.18, 18-B and 18-G read into the text')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
