-- Printed page numbers read into released provisions (15 Nov 2026): the page's last block, only 1-4 digits, at the
-- page's foot, continuing the document's page sequence (tools/recrawl/folio_patch.py: 10,038 blocks in ~1,000 released
-- documents). Held while each is set aside (patch-DOCp.json, rule reviewed_apparatus_block, no law text edited), then
-- re-verified and released. __DOCS__ is filled by the apply script.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('printed page numbers read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'printed page numbers read into released provision text; taken out of the release '
                                    'while they are set aside and the text re-verified',
                          'reverify', 'verify_text_quality is re-run after the repair')
  FROM unnest(ARRAY[__DOCS__]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d)
   AND NOT EXISTS (SELECT 1 FROM extraction_verification e
                    WHERE e.document_id = h.d AND e.reference_extractor = 'assistant-page-review-hold'
                      AND e.verified_at > (SELECT max(v.verified_at) FROM extraction_verification v
                                            WHERE v.document_id = h.d
                                              AND v.reference_extractor <> 'assistant-page-review-hold'));
COMMIT;
