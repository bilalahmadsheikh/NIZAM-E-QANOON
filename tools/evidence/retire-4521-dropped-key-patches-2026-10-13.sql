-- Doc 4521 (Regulation of Mines and Oilfields and Mineral Development (Government Control) (Amendment) Act, 2022),
-- observation 1280. Builder BZ, 13 Oct 2026, on the lead's direction (CLAUDE-CLAIMS).
--
-- The ten source-verified curation patches recorded at 18:42:22 UTC from claude/agJE/patch-4521.json were recorded
-- by tools/record_curation_patch.py at d68cc57c. That recorder listed `source_figure_subsections` in
-- STRUCTURAL_KEYS but had no branch copying it into the evidence, so patch cd2a7481 ('Short title, extent and
-- 1. This Act ...') was recorded WITHOUT its structural key, silently. The recorder now records the key (generic
-- branch) and refuses any reading whose structural key would not reach the evidence.
--
-- All ten are retired, not deleted (retired_at; precedent retire-589-order-dependent-patches-2026-09-28.sql), so the
-- record of what was first recorded stays. The same readings are then re-recorded with the fixed recorder: all ten,
-- because the nine whose evidence was complete would otherwise be refused as already recorded. Document 4521 has no
-- released expression; no replay ran on these patches.
BEGIN;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 1280
   AND retired_at IS NULL
   AND created_at = '2026-10-13 18:42:22.454413+00'
   AND id IN ('2b918d32-e915-4a3f-a77c-2f2d5c08d5b5', '8a93dfd2-dc25-401c-904c-92e80030b9b8',
              '00e52dbb-7314-4510-aae2-57d6846057d7', '9865172e-2fb0-48b9-8383-856eafddcca0',
              'fc431c4f-25fa-4564-9298-8a9b5ca6884e', '6a7d3d6f-ea4f-4763-8013-aac6fcd6f121',
              'f7b5ec3e-90e4-4da3-9cf8-2264c3c78e8c', 'c7502246-02e6-40a9-b783-3fadee3d8105',
              'cd2a7481-f60d-49cc-baf1-b8a6b926be65', 'f0eebe94-6904-4093-a783-45050e69ef26');
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch WHERE source_observation_id = 1280 AND retired_at IS NULL) <> 0
  THEN RAISE EXCEPTION 'observation 1280 still has active patches'; END IF;
END $$;
SELECT id, page_no, retired_at IS NOT NULL AS retired FROM segmentation_curation_patch
 WHERE source_observation_id = 1280 ORDER BY page_no, match_text;
COMMIT;
