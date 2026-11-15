-- AJK revised volumes (15 Nov 2026): page notes -- amendment notes and the superseded text the volumes reproduce in them
-- -- that tools/recrawl/footnote_zone.py could not take (notes at the law's size, markers it does not read, notes
-- continuing under a rule near a page's top) were read into released provisions of 19 documents. Every page was read
-- from its block dump and, where unclear, its render (tools/recrawl/ajk_note_patch.py). Held while the note blocks are
-- set aside and 12 fused law+note blocks are cut at the note's marker (patch-DOCn.json), then re-verified and released.
BEGIN;
INSERT INTO extraction_verification (document_id, verifier, reference_extractor, outcome, problems, hints, detail)
SELECT d, 'nizam.verify_text_quality/2', 'assistant-page-review-hold', 'review',
       jsonb_build_array('page notes and reproduced superseded text read into released provision text'), '[]'::jsonb,
       jsonb_build_object('reason', 'page notes (amendment notes and reproduced superseded text) read into released '
                                    'provision text; taken out of the release while they are set aside and the text '
                                    're-verified',
                          'reverify', 'verify_text_quality is re-run after the repair')
  FROM unnest(ARRAY[9994,10063,10285,10313,10482,10499,10524,10624,10668,10685,10861,10870,10912,10977,11025,11153,11167,
                    11227,11324]) AS h(d)
 WHERE EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.document_id = h.d);
COMMIT;
