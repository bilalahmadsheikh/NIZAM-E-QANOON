-- Take the three copies of President's Order 22 of 1979 (Notifications Relating to Election (Rescission) Order) out of
-- the release while their text is repaired (procedure of 7318 / 6548, 10-12 Nov 2026). Pages read on 150 dpi renders
-- and a 300 dpi crop on 12 Nov 2026 (.artifacts/release-work-2026-09-24/claude/renders/doc86{07,09,42}-p1*.png).
--   8607, 8609  the same Gazette Extraordinary page of 4 Nov 1979 (renders pixel-identical; the two drs.molaw PDFs differ
--               only in their wrapper): OCR read '1.' as '|.', so section 1 is missing; the Gazette page number '(523)'
--               opened a 'subsection 523' holding the printer's imprint and price line.
--   8642        page 393 of a code volume: the close of the preceding Order (its s.5 on cinema licences in cantonments
--               and proviso) was released as sections 5 and its proviso of P.O. 22; margin notes leak into s.2.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'released tree does not hold the printed law; taken out of the release while it is '
                                    'repaired from the page image and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (8607, 'section 1 missing (OCR read its number as a bar); the Gazette page number (523) opened a subsection '
                      'holding the printer''s imprint and price line'),
               (8609, 'section 1 missing (OCR read its number as a bar); the Gazette page number (523) opened a subsection '
                      'holding the printer''s imprint and price line'),
               (8642, 'section 5 and its proviso belong to the preceding Order printed on the same code-volume page; '
                      'side notes and margin citations leak into section 2')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at >= '2026-11-12 08:00+00');
COMMIT;

-- LIFT (after repair -r15, replay and verify_ocr, 12 Nov 2026). Lane E4: the text-quality verifier does not read these
-- documents, so the hold was their only text-quality row; this row supersedes it (form of 7585, 9310/9890).
-- Guarded: only while the hold is the latest text-quality row.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold-lifted', 'passed', '[]'::jsonb, '[]'::jsonb,
       jsonb_build_object('reason', 'hold lifted 12 Nov 2026: ' || r || '; the text-quality verifier does not apply to '
              'this document (lane E4), so the only text-quality row was the hold row, which this row supersedes; the '
              'OCR verifier row is the document evidence')
  FROM (VALUES (8607, 'the Gazette page was transcribed from its render into its blocks (patch -r15): section 1 restored, '
                      'masthead, page number (523), imprint and price set aside; tree re-built: s.1, s.1(2), s.2'),
               (8609, 'the Gazette page (pixel-identical to 8607) was transcribed into its blocks (patch -r15): section 1 '
                      'restored, masthead, page number (523), imprint and price set aside; tree re-built: s.1, s.1(2), s.2'),
               (8642, 'the code-volume page was transcribed into its blocks (patch -r15): the preceding Order''s section 5, '
                      'proviso and signature, the running head, side notes and margin citations set aside; tree re-built: '
                      's.1, s.1(2), s.2')) AS h(d, r)
 WHERE (SELECT reference_extractor FROM extraction_verification
         WHERE document_id = h.d AND verifier = 'nizam.verify_text_quality/2'
         ORDER BY verified_at DESC, id DESC LIMIT 1) = 'assistant-page-review-hold';
COMMIT;

-- COPY HOLD (12 Nov 2026). 8609 prints the same page as 8607 (renders pixel-identical); the owner-delegated answer
-- keep-8607 (decision-review-2026-10-25-delegated.json, 8607 q1) links it as a same-text copy (0062), and 0062 never
-- takes a released tree out of the release itself. This row does so, truthfully, once.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT 8609, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('same-text copy of document 8607 (the same Gazette page, pixel-identical renders); kept out of '
                         'the release so the law is published once'), '[]'::jsonb,
       jsonb_build_object('reason', 'owner-delegated decision keep-8607 (decision-review-2026-10-25-delegated.json, '
                                    'document 8607 q1); linked as duplicate_of 8607 by source_same_text_copy (0062)')
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = 8609)
   AND NOT EXISTS (SELECT 1 FROM source_same_text_copy s WHERE s.document_id = 8609);
COMMIT;
