-- DRAFT (agent K6, 19 Oct 2026; prepare mode -- the lead reviews and applies, via lead-ocr-4602.sh).
-- Doc 4602 (Sindh Workers Welfare Board Employees (Service) Rules, 2021), observation 4747.
--
-- Two digit corrections (claude.ocr-digit-review/1, 16 Sep) were recorded against 4602's OLD text layer (lane E3):
--   2f3ad8d0 p11 '35. Employ'            -> '36. Employ'
--   0c975953 p25 '121. When an employee' -> '131. When an employee'
-- The owner-accepted OCR (export ocr-review-doc-4602.json, 71/71 accepted) already reads both printed numbers right
-- ('36. Employee to abide by rules of the Board ...', '131. When an employee is on tour ...'), so after the promotion
-- neither before_text exists: each patch would raise "curation patch ... before_text is not unique" (audit S8) on every
-- segmentation of the promoted revision. Nothing is left to correct, so nothing is re-recorded: both rows are retired,
-- not deleted (retired_at; precedents retire-589, retire-4521, retire-3696, retire-4529, retire-4594), and the record of
-- what was verified stays. Neither patch belongs to a released expression (4602 has none).
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 4747
   AND retired_at IS NULL
   AND id IN ('2f3ad8d0-ccec-4987-8d61-7403538eb6d3', '0c975953-2806-4c58-9374-5ca319a134fb');
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id = 4747 AND retired_at IS NULL
         AND id IN ('2f3ad8d0-ccec-4987-8d61-7403538eb6d3', '0c975953-2806-4c58-9374-5ca319a134fb')) <> 0
  THEN RAISE EXCEPTION 'observation 4747 still has the superseded digit patches active'; END IF;
END $$;
SELECT id, page_no, before_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 4747 ORDER BY page_no;
COMMIT;
