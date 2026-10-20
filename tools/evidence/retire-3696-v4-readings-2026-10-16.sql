-- Doc 3696 (Sindh Govt. Gazette Extraordinary of 22 September 1998: the Sindh Poultry Vaccine Centre regulations),
-- observation 4624. Builder BZ, 16 Oct 2026, on the owner's decision (chat, 16 Oct: "try to release 3696 in the best
-- way ... retire old and then do it default also") relayed by the lead (CLAUDE-CLAIMS).
--
-- Batch 15 recorded agent K4's 30 readings (claude/agK4/patch-3696.json) at 16:48:35 UTC for a realignment built under
-- unreleased-v4. Observation 4624 carries RELEASED instruments, so it can never take that pin (migration 0056 -- the
-- guard stands; the drafted exception 0065 was withdrawn, never applied). Those readings are v4-shaped: one carries
-- source_part_line_blocks, and the rest were read against the v4 build. 3696 is re-prepared under DEFAULT (builder BZ,
-- with K4's rules Q and O now data-gated in every profile, group 21), and its readings are recorded afresh.
--
-- All 30 are retired, not deleted (retired_at; precedent retire-4521-dropped-key-patches-2026-10-13.sql), so the record
-- of what was first recorded stays. The released 3696 tree was built with no readings and is untouched by this.
BEGIN;
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch
       WHERE source_observation_id = 4624 AND retired_at IS NULL
         AND created_at = '2026-10-16 16:48:35.448331+00') <> 30
     OR (SELECT count(*) FROM segmentation_curation_patch
          WHERE source_observation_id = 4624 AND retired_at IS NULL) <> 30
  THEN RAISE EXCEPTION 'observation 4624: expected exactly the 30 batch-15 readings active'; END IF;
END $$;
UPDATE segmentation_curation_patch
   SET retired_at = now()
 WHERE source_observation_id = 4624
   AND retired_at IS NULL
   AND created_at = '2026-10-16 16:48:35.448331+00';
DO $$ BEGIN
  IF (SELECT count(*) FROM segmentation_curation_patch WHERE source_observation_id = 4624 AND retired_at IS NULL) <> 0
  THEN RAISE EXCEPTION 'observation 4624 still has active patches'; END IF;
END $$;
SELECT count(*) AS retired FROM segmentation_curation_patch WHERE source_observation_id = 4624 AND retired_at IS NOT NULL;
COMMIT;
