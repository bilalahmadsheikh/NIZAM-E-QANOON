-- Recrawl 14 Nov 2026 (scraper_version 'recrawl-2026-11-14/1'): six newly released laws carry a margin side note read
-- into their provision text -- the note is a block of its own (role 'body') that the default profile appended to the
-- provision before it ('... (Amendment) Act, 2018. Short title and commencement.'). Found by tools/recrawl/leakscan.py;
-- the blocks are those tools/recrawl/sidenote_strip.py --strict lists as notes AND that are assigned as body
-- (25 blocks). Each document is taken out of the release while the blocks are set aside (rule reviewed_apparatus_block,
-- patch-DOCs.json), then re-verified and released again.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'margin side notes read into released provision text; taken out of the release '
                                    'while the note blocks are set aside and the text re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (9897, '11 side-note blocks read into provision text'),
               (9898, 'side note ''Short title, extent and Commencement'' read into s.1(1)'),
               (9905, 'side notes ''Short title and commencement'', ''Board of Governors'' read into ss.1 and 3'),
               (9906, 'side note ''Short title and commencement'' read into s.1(1)'),
               (9907, '9 side-note blocks (''Amendment of section N of Sindh Act No.XLII of 2013'') read into the text'),
               (9910, 'side note ''Short title, commencement and extent'' read into s.1(1)')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at >= '2026-11-14 00:00+00');
COMMIT;
