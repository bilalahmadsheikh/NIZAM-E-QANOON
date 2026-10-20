-- Doc 4645 (the Surya OCR revision of 4364, Sind Local Government Ordinance 1979), observation 3704. Builder BZ, 17 Oct
-- 2026, on the lead's direction (batch 20; CLAUDE-CLAIMS).
--
-- Batch 20 recorded agent K6's 125 readings (claude/agBZ/patch-4645-125.json) in ONE transaction, so they share one
-- created_at and the replay applies them in id order. The replay failed: "curation patch f76b2069 matched 0 blocks".
-- Two identity readings located their block by a fragment that a text fix on the SAME block changes when the fix
-- happens to apply first (lower id):
--   f76b2069 (s.46's fused margin tail 'Works.', block 971094; match '46. A council may by laws lay down ...')
--     broken by 041b92d4 'may by laws lay down' -> 'may by bye-laws lay down';
--   2dd14b02 (the s.56 margin block 971170 set aside; match '56. (1) Government may, so moto or on application')
--     broken by 18451378 'may, so moto or' -> 'may, suo moto or'.
-- ($S/agBZ-ordercheck.py: exactly these 2 clashes among the 125.)
-- Both are retired, not deleted (retired_at; precedents retire-2479-patch-order / retire-2658-patch-order 2026-10-14),
-- and re-recorded RELOCATED from claude/agBZ/patch-4645-relocated.json on fragments no other patch touches. No replay
-- succeeded on these patches; 4645 has no released expression.
BEGIN;
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch WHERE source_observation_id = 3704 AND retired_at IS NULL
         AND id IN ('f76b2069-ff00-400e-96b2-a4b6c7e8597a', '2dd14b02-04c4-46d2-a4f7-5221d2fdb4ce')) <> 2
  THEN RAISE EXCEPTION 'observation 3704: expected the 2 order-clash patches active'; END IF;
END $$;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 3704
   AND retired_at IS NULL
   AND id IN ('f76b2069-ff00-400e-96b2-a4b6c7e8597a', '2dd14b02-04c4-46d2-a4f7-5221d2fdb4ce');
SELECT id, page_no, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 3704 AND id IN ('f76b2069-ff00-400e-96b2-a4b6c7e8597a', '2dd14b02-04c4-46d2-a4f7-5221d2fdb4ce');
COMMIT;
