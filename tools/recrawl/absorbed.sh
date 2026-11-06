#!/bin/bash
# absorbed.sh : released instruments where one parent holds >= 6 numeric clause children labelled 12+ in a run (read-only)
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tA -F '|' <<'SQL'
WITH c AS (
  SELECT i.document_id d, p.parent_id, count(*) n, min(p.label::int) lo, max(p.label::int) hi
    FROM provision p JOIN instrument i ON i.id=p.instrument_id AND i.is_active
   WHERE p.is_active AND p.kind::text='clause' AND p.label ~ '^[0-9]{1,3}$' AND p.label::int >= 12
     AND EXISTS (SELECT 1 FROM v_release_instrument r WHERE r.id=i.id)
   GROUP BY 1,2)
SELECT d, n, lo, hi FROM c WHERE n >= 6 ORDER BY n DESC;
SQL
