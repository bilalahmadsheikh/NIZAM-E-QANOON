-- ICT doc 9911 (CDA Employees Service Regulations 1992, Volume I) was released on 15 Nov 2026 by the replay that applied
-- patch-9911c.json (contents region, page numbers) and patch-9911s.json (rule reviewed_decimal_regulation_series, first
-- part). That tree still read regulations 4.21 to 25.x as rows of a TABLE declared in paragraph 16 of regulation 4.20-A
-- (pp45-52): text complete, structure wrong (a citation to regulation 5.01 resolved to nothing). The rule's second part
-- (a chapter.serial number above every regulation opened closes the table / schedule) builds the right tree, which
-- carries new repeated-label units to adjudicate; the replay gate refuses to replace a released tree with one that
-- has pending units. Held while the repaired tree is built and its units are read and settled, then re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT 9911, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('released tree reads regulations 4.21-25.x as table rows of regulation 4.20-A'), '[]'::jsonb,
       jsonb_build_object('reason', 'structure repair: regulations 4.21 to 25.x are table rows in the released tree; taken '
                                    'out of the release while the repaired tree is built and its repeated-label units '
                                    'are page-read and settled',
                          'reverify', 'verify_text_quality is re-run after the repair')
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = 9911);
COMMIT;
