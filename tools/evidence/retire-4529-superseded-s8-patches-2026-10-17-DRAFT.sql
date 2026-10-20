-- DRAFT (agent K6, 17 Oct 2026; prepare mode -- the lead reviews and applies, via lead-ocr-4529.sh).
-- Doc 4529 (SKAA Low-Cost Housing Scheme Regulations 2008), observation 4577.
--
-- Two source-verified digit corrections were recorded against 4529's OLD text layer (lane E4, tesseract):
--   a5d8232b (codex.source-image-review/2026-10-01) p8 '43. The amenity plot' -> '48. The amenity plot'
--   f0308523 (claude.ocr-digit-review/1, 16 Sep)    p9 '38. {il The change'   -> '58. {il The change'
-- The owner-accepted Surya OCR (candidates 1111-1120, export ocr-review-doc-4529.json, 10/10 accepted) already reads
-- both printed numbers right ('48. The amenity plot shall be disposed off ...', '58. (i) The change in land use ...'),
-- so after the promotion neither before_text exists: each patch locates its block but its before_text occurs 0
-- times, and every segmentation of the promoted revision raises "curation patch ... before_text is not unique"
-- (audit S8). Nothing is left to correct, so nothing is re-recorded: both rows are retired, not deleted
-- (retired_at; precedents retire-589, retire-4521, retire-3696), and the record of what was verified stays.
-- Neither patch belongs to a released expression (4529 has none).
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 4577
   AND retired_at IS NULL
   AND id IN ('a5d8232b-4d67-41b8-91c8-641a823a76a7', 'f0308523-bd3a-4bce-a5ab-64172819b543');
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id = 4577 AND retired_at IS NULL
         AND id IN ('a5d8232b-4d67-41b8-91c8-641a823a76a7', 'f0308523-bd3a-4bce-a5ab-64172819b543')) <> 0
  THEN RAISE EXCEPTION 'observation 4577 still has the superseded S8 patches active'; END IF;
END $$;
SELECT id, page_no, before_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 4577 ORDER BY page_no;
COMMIT;
