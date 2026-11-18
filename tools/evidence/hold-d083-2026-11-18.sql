-- D-083 (18 Nov 2026): two released laws held while re-segmented with page-read readings
-- (tools/evidence/heritage-2026-11-18/patch-{10935h,1336r}.json) and re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'printed headings left in released text or running heads read into it; taken out '
                                    'of the release while repaired from page-read readings and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES
    (10935, 'AJK Antiquities Act 1986: inline printed headings ("Heading.- text") left in the text of most sections'),
    (1336, 'Sindh Cultural Heritage (Preservation) Act 1994: the running-head title line read into ss.2, 7, 9, 12 '
           'and 17; s.22''s margin note read into its text')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
