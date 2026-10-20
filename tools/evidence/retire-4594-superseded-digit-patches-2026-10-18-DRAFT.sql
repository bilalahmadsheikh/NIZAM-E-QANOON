-- DRAFT (agent K6, 18 Oct 2026; prepare mode -- the lead reviews and applies, via lead-ocr-4594.sh).
-- Doc 4594 (Sindh Prisons and Corrections Services Rules, 2019), observation 4746.
--
-- Seven digit corrections (claude.ocr-digit-review/2) were recorded against 4594's OLD text layer (lane E4, tesseract):
--   7d7c917a p13 '43. Provision of funds'              -> '39. Provision of funds'
--   ef49ec46 p17 '65. All business'                    -> '69. All business'
--   512c321d p17 '65. Checking and counting'           -> '68. Checking and counting'
--   eb73f71b p18 '27. Reports and Statistics'          -> '77. Reports and Statistics'
--   ff903c0b p33 '203. Strict attention'               -> '202. Strict attention'
--   f3a9c060 p45 '273. Prohibition against sleeping'   -> '279. Prohibition against sleeping'
--   de9acfd8 p46 '283. Occurrence of Permanent Vacancy' -> '289. Occurrence of Permanent Vacancy'
-- The owner-accepted OCR (export ocr-review-doc-4594-v3.json, 159/162 accepted + 3 owner transcriptions) already reads
-- all seven printed numbers right, so after the promotion no before_text exists: each patch would raise "curation
-- patch ... before_text is not unique" (audit S8) on every segmentation of the promoted revision. Nothing is left to
-- correct, so nothing is re-recorded: the rows are retired, not deleted (retired_at; precedents retire-589,
-- retire-4521, retire-3696, retire-4529), and the record of what was verified stays.
-- None of the patches belongs to a released expression (4594 has none).
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 4746
   AND retired_at IS NULL
   AND id IN ('7d7c917a-9f4a-43bc-85f1-1d126a0fb663', 'ef49ec46-1bde-424e-9746-a0da33d7aa47',
              '512c321d-341d-4a8e-891f-d4ada3a40ddf', 'eb73f71b-f337-4977-a495-e0410650f6cb',
              'ff903c0b-0d5e-4b11-b0ba-d4d414b163d8', 'f3a9c060-1d10-498c-8dbf-df944b72a78e',
              'de9acfd8-97cb-49b3-a0d2-2effb5efa26e');
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id = 4746 AND retired_at IS NULL
         AND id IN ('7d7c917a-9f4a-43bc-85f1-1d126a0fb663', 'ef49ec46-1bde-424e-9746-a0da33d7aa47',
                    '512c321d-341d-4a8e-891f-d4ada3a40ddf', 'eb73f71b-f337-4977-a495-e0410650f6cb',
                    'ff903c0b-0d5e-4b11-b0ba-d4d414b163d8', 'f3a9c060-1d10-498c-8dbf-df944b72a78e',
                    'de9acfd8-97cb-49b3-a0d2-2effb5efa26e')) <> 0
  THEN RAISE EXCEPTION 'observation 4746 still has the superseded digit patches active'; END IF;
END $$;
SELECT id, page_no, before_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 4746 ORDER BY page_no;
COMMIT;
