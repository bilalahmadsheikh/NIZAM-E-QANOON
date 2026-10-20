-- DRAFT (agent K6, 19 Oct 2026; prepare mode -- the lead reviews and applies, via lead-ocr-4590.sh).
-- Doc 4590 (Sindh Mines and Minerals Governance Rules, 2023), observation 4750.
--
-- One digit correction (claude.ocr-digit-review/1, 16 Sep) was recorded against 4590's OLD text layer (lane E4,
-- tesseract):
--   308e33d1 p28 '30. Application for Amendment' -> '39. Application for Amendment'
-- The owner-accepted OCR (export ocr-review-doc-4590.json, 88/88 accepted) already reads the printed number right
-- ('39. Application for Amendment of Mineral Deposit Retention License ...'), so after the promotion the before_text no
-- longer exists: the patch would raise "curation patch ... before_text is not unique" (audit S8) on every segmentation
-- of the promoted revision. Nothing is left to correct, so nothing is re-recorded: the row is retired, not deleted
-- (retired_at; precedents retire-589, retire-4521, retire-3696, retire-4529, retire-4594, retire-4602), and the record
-- of what was verified stays. The patch belongs to no released expression (4590 has none).
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 4750
   AND retired_at IS NULL
   AND id = '308e33d1-47c1-47f3-98e8-2f89da3ac8ca';
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id = 4750 AND retired_at IS NULL
         AND id = '308e33d1-47c1-47f3-98e8-2f89da3ac8ca') <> 0
  THEN RAISE EXCEPTION 'observation 4750 still has the superseded digit patch active'; END IF;
END $$;
SELECT id, page_no, before_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 4750 ORDER BY page_no;
COMMIT;
