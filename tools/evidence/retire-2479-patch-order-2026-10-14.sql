-- Doc 2479 (Provincial Employees' Social Security (Contributions) Regulations 1967), observation 2279. Builder BZ,
-- 14 Oct 2026 (CLAUDE-CLAIMS). Precedent: retire-589-order-dependent-patches-2026-09-28.sql.
--
-- Two of agent JA's readings (claude/agJA/patch-2479.json), recorded together at 2026-10-13 20:39:22, move the
-- wrapped heading line of regulation 3 'amount of contribution' from block 205214 up into block 205213:
--   00e45ceb  p1 'Manner of calculating daily wages for purpose'  'determining the' -> 'determining the amount of contribution'
--   c5bf846a  p1 'amount of contribution'                         'amount of contribution' -> ''
-- The segmenter applies an observation's patches in (page_no, created_at, id) order; both share one created_at, so
-- 00e45ceb ran first and c5bf846a's locator then matched two blocks. The replay failed closed ('matched 2 blocks;
-- expected 1') before writing anything. No locator can tell the two blocks apart once 00e45ceb has run, so the ORDER is
-- fixed instead: 00e45ceb is retired (not deleted) and the same reading is re-recorded later with a shortened locator
-- (claude/agBZ/patch-2479-reordered.json), so it applies after c5bf846a. The readings themselves are unchanged.
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 2279 AND retired_at IS NULL
   AND id = '00e45ceb-48a1-48da-93b0-dd838e3ece68';
SELECT id, page_no, match_text, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 2279 AND page_no = 1 ORDER BY created_at, id;
COMMIT;
