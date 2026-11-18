-- Advance exact-duplicate links whose canonical was re-materialized (post-replay step 2-dup, 18 Nov 2026).
--
-- Step 2 of tools/post_replay_sequence.sh re-materializes the multi-expression documents after step 1 has re-linked
-- exact duplicates, so an active duplicate row can be left with duplicate_of on the RETIRED canonical of its own
-- expression (44 rows in docs 1970, 3392 and 4497 on 18 Nov). The retired-revision prune then refuses to run
-- ("retained instrument references a prune target"). Each such link moves to the one active canonical instrument of
-- the same observation and expression ordinal. Idempotent; fails if a link would still point at a retired row.
BEGIN;
WITH stale AS (
  SELECT i.id, cur.id AS successor
    FROM instrument i
    JOIN instrument t ON t.id = i.duplicate_of AND NOT t.is_active
    JOIN instrument cur ON cur.is_active AND cur.duplicate_of IS NULL
                       AND cur.source_observation_id = t.source_observation_id
                       AND cur.expression_ordinal = t.expression_ordinal
   WHERE i.is_active
)
UPDATE instrument i SET duplicate_of = s.successor FROM stale s WHERE i.id = s.id;
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM instrument i JOIN instrument t ON t.id = i.duplicate_of
              WHERE i.is_active AND NOT t.is_active) THEN
    RAISE EXCEPTION 'an active duplicate still names a retired canonical';
  END IF;
END $$;
COMMIT;
