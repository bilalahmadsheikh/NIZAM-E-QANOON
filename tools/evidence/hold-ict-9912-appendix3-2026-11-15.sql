-- ICT doc 9912 (CDA Employees Service Regulations 1992, Volume II, the Appendices) was released on 15 Nov 2026 by the
-- replay that applied its appendix openers, contents region and page-number set-asides (patch-9912a/r/n.json). Its
-- Appendix-3 (p140) is a scanned image of S.R.O. No. 747(1)/2020; the text layer carries only the heading, so the
-- released appendix is the heading alone. Held while the image's text, transcribed from the page render
-- (patch-9912t.json), is added and the text re-verified.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT 9912, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('Appendix-3 text is an image; released appendix holds only its heading'), '[]'::jsonb,
       jsonb_build_object('reason', 'Appendix-3 (p140) prints S.R.O. No. 747(1)/2020 as a scanned image the text layer '
                                    'lacks; taken out of the release while the transcription is added',
                          'reverify', 'verify_text_quality is re-run after the repair')
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = 9912);
COMMIT;
