-- 18 Nov 2026: after the D-085 replays the post-replay sequence re-materialized the multi-expression documents 1970,
-- 3392 and 4497 (step 2) AFTER re-linking exact duplicates (step 1), so 44 active duplicate rows kept duplicate_of on
-- the retired canonical of the same expression. The retired-revision prune refuses that ("retained instrument
-- references a prune target"). Advance each link to the one active canonical instrument of the same observation and
-- expression ordinal -- the lineage advance tools/resolve_exact_instrument_duplicates.py makes for replayed canonicals.
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
