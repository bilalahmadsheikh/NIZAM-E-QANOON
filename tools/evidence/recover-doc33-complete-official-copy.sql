-- Source-reviewed recovery of the complete official publication for the
-- Nawab Shaheed Ghous Bakhsh Raisani Memorial Hospital Act, 2012.
--
-- The Balochistan Code observation 1358 is a three-page derivative which ends
-- during section 5.  Observation 9573 is the nine-page Gazette scan published
-- by the Balochistan Health Department (SHA-256 d324...0098).  Every rendered
-- page in .review/doc33/health-page-{1..9}.png was read against the Surya
-- candidate.  The scan prints sections 1 through 19 and the Secretary's close.
-- Tesseract remains immutable in document 4633; these decisions select the
-- independent, materially cleaner Surya reading for an append-only revision.

BEGIN;

DO $$
DECLARE
    page_total integer;
    candidate_total integer;
BEGIN
    SELECT count(*) INTO page_total FROM page WHERE document_id=4633;
    SELECT count(*) INTO candidate_total
      FROM page_ocr_candidate
     WHERE document_id=4633
       AND engine='surya-ocr-0.22.1+surya-2-gguf+llama.cpp-b10516';
    IF page_total<>9 OR candidate_total<>9 THEN
        RAISE EXCEPTION 'expected 9 source pages and 9 Surya candidates; got % and %',
                        page_total,candidate_total;
    END IF;
END $$;

INSERT INTO page_ocr_adjudication
    (candidate_id,decision,reason,evidence,decided_by)
SELECT c.id,'accepted',
       'Direct source-render review: complete official Gazette reading.',
       jsonb_build_object(
           'review','direct-source-render',
           'basis','each of the nine candidate pages compared with its rendered official source page',
           'source_observation_id',9573,
           'source_pdf_sha256','d3242860e7fb2da362b7a89e99ac5741781fcede78250e8b05f581b883d30098',
           'document_id',c.document_id,
           'page_no',c.page_no,
           'render_artifact',format('.review/doc33/health-page-%s.png',c.page_no),
           'render_sha256',(ARRAY[
             'e70de4a739cb9589b616e7d177099fe8cc16f8b9e4da25986719bd5378c9c4c2',
             '383515df9be9ff67dda259bbd13d403e551d2cbe0ef29b0c3d4686dc71e39777',
             'ee641c5b1eff4a02b95a968d39a7fc25674faffb4400248749439f2e7c5ea504',
             '0664d5c0212a0a327586ebeaf2b67f64ba69666dfc026900a1b79c10e01f4413',
             'c67fbc6c1bb11722e2138299cc27a088750360da293c60ae9e8098f8a3d4e10a',
             '8bf3952b23ec25c66a9e406d41d8fade9d5b7aa3aeff30952397edc7f5846465',
             '1b5c7bf50075b793b1d42eed57a31afef1b2e7a0c246c169b75fa8018b0c9e9c',
             'f71234716d7be1eed8905edfcdf196714361e4b8395faeda9fd5d090bad92147',
             'e852c4e2e1dca9c96a8714801cf205a648fc445e9a5bcc599a1a1d561051a446'
           ])[c.page_no],
           'candidate_engine',c.engine,
           'candidate_confidence',round(c.mean_confidence,4),
           'coverage','all source pages',
           'reviewed_section_range','1-19'
       ),
       'nizam.source_review/codex-2026-09-13'
  FROM page_ocr_candidate c
 WHERE c.document_id=4633
   AND c.engine='surya-ocr-0.22.1+surya-2-gguf+llama.cpp-b10516'
ON CONFLICT (candidate_id,decision,reason) DO NOTHING;

-- Three exact, page-verified character repairs are applied only to the
-- derived segmentation input.  The accepted OCR candidate remains immutable.
INSERT INTO segmentation_curation_patch
    (source_observation_id,page_no,match_text,before_text,after_text,evidence,
     review_state,created_by)
VALUES
 (9573,4,'Additional Chief Secretary (Dex)','(Dex)','(Dev.)',
  jsonb_build_object(
    'defect','Surya read the printed abbreviation Dev. as Dex',
    'document_id',4633,
    'render_artifact','.review/doc33/health-page-4.png',
    'render_sha256','0664d5c0212a0a327586ebeaf2b67f64ba69666dfc026900a1b79c10e01f4413',
    'source_pdf_sha256','d3242860e7fb2da362b7a89e99ac5741781fcede78250e8b05f581b883d30098'),
  'source_verified','nizam.source_review/codex-2026-09-13'),
 (9573,7,'The budget of a Hospital shall be approved','14 (1)','14. (1)',
  jsonb_build_object(
    'defect','section 14 stop omitted by OCR',
    'document_id',4633,
    'render_artifact','.review/doc33/health-page-7.png',
    'render_sha256','1b5c7bf50075b793b1d42eed57a31afef1b2e7a0c246c169b75fa8018b0c9e9c',
    'source_pdf_sha256','d3242860e7fb2da362b7a89e99ac5741781fcede78250e8b05f581b883d30098'),
  'source_verified','nizam.source_review/codex-2026-09-13'),
 (9573,7,'The Board with approval of the Government may','17 (1)','17. (1)',
  jsonb_build_object(
    'defect','section 17 stop omitted by OCR',
    'document_id',4633,
    'render_artifact','.review/doc33/health-page-7.png',
    'render_sha256','1b5c7bf50075b793b1d42eed57a31afef1b2e7a0c246c169b75fa8018b0c9e9c',
    'source_pdf_sha256','d3242860e7fb2da362b7a89e99ac5741781fcede78250e8b05f581b883d30098'),
  'source_verified','nizam.source_review/codex-2026-09-13')
ON CONFLICT (source_observation_id,page_no,match_text,before_text) DO NOTHING;

COMMIT;
