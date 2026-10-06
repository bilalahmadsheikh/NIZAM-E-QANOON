-- Doc 589 (Sind Finance (Amendment) Ordinance, 1980), observation 3949.
--
-- Two of the six source-verified curation patches recorded on 28 Sep 2026 used a
-- locator (match_text) that another patch's after_text also contains:
--   ef1c0a29  p1 '3 ½ percent of energy charges'  -- also in 94f179c3's after_text
--   c3d7bd48  p2 '3 paisa per unit of energy'     -- also in 1120aed2's after_text
-- The segmenter applies an observation's patches in (page_no, created_at, id)
-- order; all six share one created_at, so 94f179c3 and 1120aed2 run first and
-- the two locators then match two blocks. The replay fails closed
-- ("matched 2 blocks; expected 1") and the stored tree was left unchanged.
--
-- The readings themselves are unchanged. They are re-recorded with locators that
-- no other patch's after_text contains ('6 percent of energy charges',
-- '2 paisa per unit of energy'). The originals are retired, not deleted
-- (retired_at, as migration 0025's active-patch index anticipates), so the record
-- of what was first recorded stays.
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 3949
   AND retired_at IS NULL
   AND id IN ('ef1c0a29-a799-4a7f-a005-18e48cc84cb7', 'c3d7bd48-310b-4786-a05d-90290831b5d2');
SELECT id, page_no, match_text, retired_at IS NOT NULL AS retired
  FROM segmentation_curation_patch WHERE source_observation_id = 3949 ORDER BY page_no, match_text;
COMMIT;
