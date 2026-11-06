#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -At -F ' | ' <<'SQL'
WITH q AS (SELECT i.*, o.source_metadata->>'listing' listing FROM instrument i JOIN source_observation o ON o.id=i.source_observation_id
            WHERE i.is_active AND i.duplicate_of IS NULL AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id))
SELECT CASE WHEN year IS NULL THEN 'undated' WHEN year < 1947 THEN '<1947' WHEN year < 1973 THEN '1947-1972' WHEN year < 2000 THEN '1973-1999'
            WHEN year < 2020 THEN '2000-2019' ELSE '2020+' END era, count(*),
       count(*) FILTER (WHERE kind::text IN ('act','ordinance')) acts_ords
  FROM q GROUP BY 1 ORDER BY 1;
WITH q AS (SELECT i.*, o.source_id, o.source_metadata->>'listing' listing FROM instrument i JOIN source_observation o ON o.id=i.source_observation_id
            WHERE i.is_active AND i.duplicate_of IS NULL AND NOT EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id) AND i.year >= 2020)
SELECT source_id, coalesce(listing,'(old catalogue)'), count(*), string_agg(left(short_title,45), ' ; ' ORDER BY year DESC) FILTER (WHERE true) FROM q GROUP BY 1,2 ORDER BY 3 DESC LIMIT 12;
SQL
