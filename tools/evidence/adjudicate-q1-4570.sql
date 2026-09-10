-- Accept the Surya reading for 4570, the last Q1 document, with its caveats.
--
-- 4570 is the Balochistan Local Council by-laws on registration of births and
-- deaths. Its first Surya pass returned zero blocks for pages 13 and 15, so it
-- was held back from the fifteen-document batch: promoting it then would have
-- written a document with two holes, which `promote_ocr_adjudicated` refuses.
--
-- Both pages were then re-read, and what defeated each one is worth recording
-- because neither is a Nastaliq problem:
--
--   PAGE 13, a faint bilingual death-registration form, was read at 300 DPI
--   against Surya's default of roughly 192. Confidence 0.9653, 440 words. The
--   reading is plainly correct: the form title, the Normal / Late Death Entry
--   checkboxes and the numbered bilingual field labels all match the source.
--
--   PAGE 15, a register table rotated 90 degrees inside the scan, needed three
--   changes and the third is the one that mattered. De-rotating alone did not
--   work. Cropping to the content and lifting the contrast did not work either:
--   Surya timed out three times, roughly 28 minutes each. It is a 13-column
--   ruled grid whose rows are empty, and the timeouts are consistent with the
--   model generating table markup for those empty cells until the token budget
--   is gone. Excluding the empty rows and giving it only the title and column-
--   header band returned a reading in 160 seconds. Confidence 0.9035, 91 words.
--
-- CAVEAT ONE -- page 15 has known transcription errors. Against the source
-- render: `محل` appears where the page reads `ضلع` (district), and `صفحہ فہر`
-- where it reads `صفحہ نمبر` (page number). The reading is far better than the
-- Tesseract text it replaces, and it is not clean.
--
-- CAVEAT TWO -- pages 13 and 15 carry derived geometry. Their blocks come from
-- re-rendered images: page 13 rescaled, page 15 rotated, contrast-stretched and
-- twice cropped. The importer scales bounding boxes from image space to page
-- points, so the text and reading order are right while the coordinates are an
-- approximation of where the words sit on the original page. Page 15's recorded
-- dpi of 222 is an artifact of that transformation, not the 300 it was rendered
-- at. Anything that later trusts these boxes as true page geometry -- an overlay,
-- a crop-back to the source, a spatial join -- must read this first.
--
-- WHAT WAS NOT DISCARDED. Cropping away part of page 15 is exactly the move the
-- corpus rule forbids doing carelessly, so the excluded band was measured and
-- looked at rather than assumed: 3,263 dark pixels across 394 rows, and the
-- render shows ruled lines only -- no glyphs, no handwriting, no entries. The
-- crop removed the empty grid of a blank register and no content. The original
-- zero-block candidates for both pages are also retained beside the successful
-- ones; evidence is never pruned (C7).

BEGIN;

-- The decision itself: the strongest Surya candidate for each of the 19 pages.
INSERT INTO page_ocr_adjudication
    (candidate_id, decision, reason, evidence, decided_by)
SELECT c.id, 'accepted',
       'Q1 review: Surya reading accepted over the stored Tesseract reading.',
       jsonb_build_object(
           'review', 'q1-adjudication-ledger',
           'basis', 'representative page compared side by side; pages 13 and 15 read from source renders',
           'document_id', c.document_id,
           'page_no', c.page_no,
           'candidate_confidence', round(c.mean_confidence, 4),
           'stored_document_confidence', 0.3896,
           'candidate_engine', c.engine,
           'coverage', 'all 19 pages carry a candidate after the page 13 and 15 repair',
           'caveats', CASE
               WHEN c.page_no = 15 THEN
                   jsonb_build_array('known transcription errors: محل for ضلع, صفحہ فہر for صفحہ نمبر',
                                     'derived geometry: rotated, contrast-lifted and cropped render',
                                     'empty table rows excluded from the OCR input; verified to hold ruled lines only')
               WHEN c.page_no = 13 THEN
                   jsonb_build_array('derived geometry: 300 DPI re-render')
               ELSE '[]'::jsonb END
       ),
       'bilalahmadsheikh'
  FROM page_ocr_candidate c
 WHERE c.engine LIKE 'surya%'
   AND c.document_id = 4570
   AND c.id = (SELECT c2.id FROM page_ocr_candidate c2
                WHERE c2.document_id = c.document_id AND c2.page_no = c.page_no
                  AND c2.engine LIKE 'surya%'
                ORDER BY c2.mean_confidence DESC NULLS LAST, c2.id DESC LIMIT 1)
ON CONFLICT (candidate_id, decision, reason) DO NOTHING;

-- Caveat one, against the page it belongs to.
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT d.sha256, 15, 'decode_damage',
       'Direct source-render review: the accepted Surya reading of page 15 '
       'misreads two column headings -- محل for ضلع (district) and صفحہ فہر for '
       'صفحہ نمبر (page number). Accepted regardless: it replaces Tesseract text '
       'that carried no readable Urdu at all. Recorded so the error is visible '
       'rather than hidden behind the document confidence of 0.9635.',
       jsonb_build_object(
           'document_id', 4570,
           'known_errors', jsonb_build_array(
               jsonb_build_object('read', 'محل', 'source', 'ضلع', 'meaning', 'district'),
               jsonb_build_object('read', 'صفحہ فہر', 'source', 'صفحہ نمبر', 'meaning', 'page number')),
           'candidate_confidence', 0.9035,
           'review', 'direct-render'),
       'bilalahmadsheikh'
  FROM document d WHERE d.id = 4570 AND d.is_active;

-- Caveat two, for both repaired pages.
INSERT INTO extraction_assertion (sha256, page_no, kind, evidence, detail, asserted_by)
SELECT d.sha256, p.page_no, 'visibility_review',
       'Block geometry for this page is derived, not measured. The accepted '
       'reading comes from a re-rendered image rather than Surya''s own render '
       'of the PDF page, so bounding boxes are scaled from a transformed image '
       'and approximate where the words sit on the source page. Text and reading '
       'order are unaffected. Do not treat these boxes as true page coordinates.',
       jsonb_build_object(
           'document_id', 4570,
           'transform', CASE WHEN p.page_no = 15
               THEN 'rotate 90; crop to content; contrast stretch; crop to header band'
               ELSE 'render at 300 DPI' END,
           'recorded_dpi_is_artifact', p.page_no = 15,
           'true_render_dpi', 300),
       'bilalahmadsheikh'
  FROM document d CROSS JOIN (VALUES (13), (15)) AS p(page_no)
 WHERE d.id = 4570 AND d.is_active;

COMMIT;
