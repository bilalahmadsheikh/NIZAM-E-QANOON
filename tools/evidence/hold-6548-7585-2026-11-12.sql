-- Take 6548 and 7585 out of the release while their text is repaired (procedure of 7318, 10 Nov 2026).
-- Both pages were read on 200/150 dpi renders on 12 Nov 2026 (.artifacts/release-work-2026-09-24/claude/renders/).
--   6548  The Unani, Ayurvedic and Homoeopathic Practitioners (Repeal) Ordinance, 1959 (one Gazette page, E2 OCR):
--         the OCR garbled sections 1-2 and the segmenter set them aside as preface; the released tree's only
--         provision is the Gazette page number and price line '( 501 ) Price: Anna 1'.
--   7585  Balochistan S&GAD notification of April 2024 amending the Education Department (Collegiate Branch) (Men's
--         Section) (BPS-16 and above) Service Rules 2020 (one page, E4): the released tree's only provision is a
--         'section 7' made from item 7 of the distribution list, text 'Page 1 of 2'; the amendment itself is not in
--         the tree.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review', jsonb_build_array(p), '[]'::jsonb,
       jsonb_build_object('reason', 'released tree does not hold the printed law; taken out of the release while it is '
                                    'repaired from the page image and re-verified',
                          'reverify', 'verify_text_quality and the full verifier chain are re-run after the repair')
  FROM (VALUES (6548, 'released tree holds only the Gazette page number and price line; sections 1 and 2 (garbled OCR) '
                      'were set aside as preface'),
               (7585, 'released tree holds only a section 7 made from item 7 of the distribution list (text ''Page 1 '
                      'of 2''); the notification''s amendment is not in the tree')) AS h(d, p)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   -- once only: a re-run of this file after the repair must not hold the repaired documents again
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at >= '2026-11-11 21:00+00');
COMMIT;

-- LIFT (after repair, replay and verify_ocr, 12 Nov 2026). 6548 needed none: verify_text_quality/2 itself appended a
-- passing row. 7585 is lane E4, which the text-quality verifier does not read, so its only text-quality row was the
-- hold; this row supersedes it, in the form of the 9310/9890 lifts (11 Nov). Guarded: only while the hold is the latest.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT 7585, 'nizam.verify_text_quality/2', 'assistant-page-review-hold-lifted', 'passed', '[]'::jsonb, '[]'::jsonb,
       jsonb_build_object('reason', 'hold lifted 12 Nov 2026: the notification was transcribed from the page render into '
              'its one block (patch -r14), opened as the unnumbered root provision NOTIFICATION under profile '
              'unreleased-v4 (precedent doc 1970), the distribution list and footer set aside, and the tree re-built; '
              'the text-quality verifier does not apply to this document (lane E4), so the only text-quality row was the '
              'hold row, which this row supersedes; the OCR verifier row is the document evidence')
 WHERE (SELECT reference_extractor FROM extraction_verification
         WHERE document_id = 7585 AND verifier = 'nizam.verify_text_quality/2'
         ORDER BY verified_at DESC, id DESC LIMIT 1) = 'assistant-page-review-hold';
COMMIT;
