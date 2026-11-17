-- 17 Nov 2026: the federal Pakistan Penal Code (document 4441) carries its page footnotes in released provision text.
-- 23 footnote blocks on 23 pages were assigned role 'body' (168 others were correctly 'footnote'); in two more
-- blocks (pp. 93, 97) the footnotes are printed in the same text block as ss.244 and 268. Effects seen in the
-- served law: five false sections ('499' and '70' after s.4, '1S' and '2' after s.153A, '1S' after s.170) -- the
-- false '70' holding s.4's clauses (1)-(4) and Explanation -- and footnote wording inside some 30 sections, several
-- mid-sentence across a page break (s.390). Held while the blocks are set aside or re-read
-- (.artifacts/recrawl-queue/specs/blockfix-4441.json, rule reviewed_apparatus_block), then re-verified and released.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('page footnotes read into released provision text; footnote numbers opened false sections'),
       '[]'::jsonb,
       jsonb_build_object('reason', 'page footnotes read into released provision text (25 blocks, pp. 30-176); '
                                    'taken out of the release while the footnote blocks are set aside and the text '
                                    're-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM unnest(ARRAY[4441]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
