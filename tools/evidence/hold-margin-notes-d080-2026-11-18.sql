-- D-080 (18 Nov 2026): four released laws whose printed margin headings were read into their text or lost, held while
-- re-segmented with page-read readings (tools/evidence/heritage-2026-11-18/patch-{4788n,4986n,5133h,1336n}.json)
-- and re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'printed margin headings read into released provision text or missing; taken out '
                                    'of the release while repaired from page-read readings and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES
    (4788, 'Balochistan Cultural Heritage Preservation Act 2010: the margin-column notes of all 18 sections read line '
           'by line into the text; no section carries its heading'),
    (4986, 'Balochistan Antiquities Act 2014: the margin notes of 42 sections read into the text of the section before; '
           'no section carries its heading'),
    (5133, 'KP Antiquities Act 2016 s.10: headed by the contents row with the Code''s closing bracket; its printed '
           'heading and sub-section (1) left as one text'),
    (1336, 'Sindh Cultural Heritage (Preservation) Act 1994 s.8(1): ends with the margin note of s.8')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
