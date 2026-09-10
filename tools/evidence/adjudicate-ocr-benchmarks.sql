-- Record the source-visible conclusions of the bounded OCR benchmark.
-- Candidates remain stored even when rejected.
INSERT INTO page_ocr_adjudication
    (candidate_id,decision,reason,evidence,decided_by)
SELECT c.id,'rejected',
       'Representative source-page review found material Urdu word or section-notation errors.',
       jsonb_build_object(
           'review','direct-render',
           'document_id',4503,
           'page_no',1,
           'finding','Tesseract variants scored 0.2527-0.5138 and did not preserve the title and provision notation.'
       ),
       'codex-source-cross-review'
  FROM page_ocr_candidate c
 WHERE c.document_id=4503 AND c.page_no=1
   AND c.engine LIKE 'tesseract-%+ensemble-v1'
ON CONFLICT (candidate_id,decision,reason) DO NOTHING;

INSERT INTO page_ocr_adjudication
    (candidate_id,decision,reason,evidence,decided_by)
SELECT c.id,'rejected',
       'Direct source-page review found material Urdu word and section-notation errors.',
       jsonb_build_object(
           'review','direct-render',
           'document_id',4503,
           'page_no',1,
           'examples',jsonb_build_array(
               'تعزاریات instead of تعزیرات',
               '۱ یکٹ instead of ایکٹ',
               'incorrect section 130-A rendering'
           )
       ),
       'codex-source-cross-review'
  FROM page_ocr_candidate c
 WHERE c.document_id=4503 AND c.page_no=1
   AND c.engine LIKE 'surya-%'
ON CONFLICT (candidate_id,decision,reason) DO NOTHING;

INSERT INTO page_ocr_adjudication
    (candidate_id,decision,reason,evidence,decided_by)
SELECT c.id,'rejected',
       'A source-confirmed four-block transcription was promoted in a successor revision; this alternate reading is retained only as evidence.',
       jsonb_build_object(
           'review','two-official-render-cross-check',
           'successor_document_id',4615,
           'assertion_id',13
       ),
       'codex-source-cross-review'
  FROM page_ocr_candidate c
 WHERE c.document_id=567 AND c.page_no=5
ON CONFLICT (candidate_id,decision,reason) DO NOTHING;
