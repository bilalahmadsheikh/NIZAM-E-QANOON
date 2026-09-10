-- This four-page amendment is primarily a penalty-rate schedule.  Its OCR is
-- high confidence and source-complete, but a statutory-function-word ratio is
-- the wrong plausibility signal for rows such as offence names and rupee rates.
-- Record the full-document visual review rather than lowering the corpus-wide
-- language threshold.

BEGIN;

INSERT INTO extraction_assertion
       (sha256,page_no,kind,evidence,detail,asserted_by)
SELECT 'b85b255379874e054409ecc3481719e2aa8ccae831cfb08b4e32dfa396d2d037',
       NULL,'source_content_confirmed',
       'Direct rendering of all four pages confirms one page of amendment text followed by penalty-rate tables and explanatory notes. The 0.210 legal-token rate reflects table vocabulary; OCR confidence is 0.903 with 1,236 accepted words.',
       '{"method":"direct-render-review","render_dpi":150,"purpose":"ocr-table-document","pages_reviewed":[1,2,3,4]}'::jsonb,
       'codex-direct-visual-review'
 WHERE NOT EXISTS (
       SELECT 1 FROM extraction_assertion
        WHERE sha256='b85b255379874e054409ecc3481719e2aa8ccae831cfb08b4e32dfa396d2d037'
          AND page_no IS NULL AND kind='source_content_confirmed' AND is_active
          AND detail->>'purpose'='ocr-table-document'
 );

COMMIT;
