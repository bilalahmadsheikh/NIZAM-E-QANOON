-- Accept the Surya reading for the fifteen Q1 documents with full page coverage.
--
-- Every one of the sixteen documents failing Q1 fails on OCR confidence below
-- the 0.70 floor, and fifteen of them now have a complete second reading from
-- surya-ocr-2. The stored Tesseract reading is retained: rejecting or replacing
-- a candidate never deletes it, and promotion retires the old revision rather
-- than dropping it (migration 0012).
--
-- 4570 is deliberately absent. Surya returned zero blocks for its pages 13 and
-- 15 -- a faint bilingual death-registration form and a register table rotated
-- 90 degrees inside the scan -- so its reading is incomplete at 17 of 19 pages.
-- Those two pages are being re-read; until they are, promoting 4570 would write
-- a document with holes, and `promote_ocr_adjudicated` refuses it.
--
-- WHAT THE REVIEWER SAW, stated exactly, because the evidence field is a record
-- of method and not a claim of thoroughness: the Q1 adjudication ledger, which
-- shows for each document the aggregate stored and proposed confidence, the
-- flagged problems, and ONE representative page -- the page with the most
-- recovered words -- with the stored text beside the proposed text in Nastaliq.
-- It is not a page-by-page collation of all 90 pages against the source.
--
-- Supporting measurements, all recorded elsewhere in this run:
--   * confidence 0.346-0.682 stored -> 0.947-0.991 proposed, floor 0.70
--   * the Tesseract ensemble alternative gained only 0.018-0.070 and reached
--     the floor on none of the five English documents
--   * legal-token rate rises 29-66% relative on clean text (0.260 -> 0.344,
--     0.334 -> 0.432, 0.256 -> 0.426), which is what clears 4613's second
--     problem (0.248 against a 0.25 floor) without a table-document assertion

BEGIN;

INSERT INTO page_ocr_adjudication
    (candidate_id, decision, reason, evidence, decided_by)
SELECT c.id, 'accepted',
       'Q1 review: Surya reading accepted over the stored Tesseract reading.',
       jsonb_build_object(
           'review', 'q1-adjudication-ledger',
           'basis', 'representative page compared side by side; aggregate confidence and coverage',
           'document_id', c.document_id,
           'page_no', c.page_no,
           'candidate_confidence', round(c.mean_confidence, 4),
           'stored_document_confidence', (SELECT round(d.printable_ratio, 4)
                                            FROM document d
                                           WHERE d.id = c.document_id AND d.is_active),
           'candidate_engine', c.engine,
           'coverage', 'all pages of this document carry a candidate'
       ),
       'bilalahmadsheikh'
  FROM page_ocr_candidate c
 WHERE c.engine LIKE 'surya%'
   AND c.document_id IN (4503, 4504, 4505, 4506, 4507, 4509, 4511, 4512,
                         4519, 4526, 4539, 4546, 4567, 4604, 4613)
   -- the strongest Surya candidate for each page, and only that one
   AND c.id = (SELECT c2.id
                 FROM page_ocr_candidate c2
                WHERE c2.document_id = c.document_id
                  AND c2.page_no = c.page_no
                  AND c2.engine LIKE 'surya%'
                ORDER BY c2.mean_confidence DESC NULLS LAST, c2.id DESC
                LIMIT 1)
ON CONFLICT (candidate_id, decision, reason) DO NOTHING;

COMMIT;
