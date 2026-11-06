#!/bin/bash
# find_title.sh "pattern1" ["pattern2" ...] : instruments whose title matches all ILIKE patterns (doc, year, released)
cd /mnt/e/Nizam_e_Qanoon
W=""; for p in "$@"; do W="$W AND i.short_title ILIKE '%$p%'"; done
./nz psql -tA -F ' | ' -c "SELECT i.document_id, i.year, EXISTS(SELECT 1 FROM v_release_instrument r WHERE r.id=i.id), left(i.short_title,80) FROM instrument i WHERE i.is_active AND i.duplicate_of IS NULL $W ORDER BY 1"
