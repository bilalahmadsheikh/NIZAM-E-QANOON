-- Docs 4501 (Code of Criminal Procedure, 1898) and 4392 (General Clauses Act, 1897): footnotes printed below the page
-- rule were read into law text and opened false sections. CrPC p28: the note numbers 'Ext. p. 1327-A' opened a section
-- '1327-A' holding s.4(1) clauses (i)-(w) and s.4(2). GCA: '1CI', '3CI' and '1I' (note numbers glued to 'Cl.' and
-- 'I.e.') opened false sections holding s.3(37a)-(59); 23 inserted definitions ran on inside the one before them.
-- Five more laws (1992, 2840, 3717, 3958, 4301) carry one false section each, opened by a notes block ('1I.e.', '1CI.').
-- Found 21 Nov 2026 while measuring retrieval assembly (D-110). Held while re-segmented under the page-read readings
-- in tools/evidence/footnote-sections-2026-11-21/ and re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'footnotes read into law text opened false sections; taken out of the release '
                                    'while repaired and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (4501, 'p28 footnotes read into s.4(1)(h); a false section ''1327-A'' holds s.4(1)(i)-(w) and s.4(2)'),
               (4392, 'footnotes on every page read into s.3 and later sections; false sections ''1CI'', ''3CI'', '
                      '''1I'' hold s.3(37a)-(59); inserted definitions (3c) (8)-(9a) (13a) (14) (20) (21) (27) (34a1) '
                      '(34a) (37)-(37b) (43ai) (43a) (55a) (56)-(58) not opened'),
               (1992, 'p8 footnote block read as law; a false section ''1'' demoted the real s.1 to a clause'),
               (2840, 'p2 footnote ''1I.e., the 7th October, 1960'' opened a false section ''1I'''),
               (3717, 'p4 footnote ''1I.e. the 16th day of May, 1977'' opened a false section ''1I'' holding s.2(1)(b)-(h)'),
               (3958, 'p2 footnote ''1I.e. 15th April, 1979'' opened a false section ''1I'''),
               (4301, 'p4 footnote ''1CI. (c) omitted'' opened a false section ''1CI'' holding s.2(1)(q)-(s)')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
