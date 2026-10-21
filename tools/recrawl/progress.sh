#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
for s in federal sindh balochistan kp drs0 drs1 drs2; do
  tot=$(wc -l < $O/missing-$s.jsonl 2>/dev/null)
  last=$(grep -E "^[0-9]+/[0-9]+ landed|^landed " $O/land-$s.log 2>/dev/null | tail -1)
  ex=$(grep -c "^exit" $O/land-$s.log 2>/dev/null)
  echo "$s total=$tot  last: ${last:-none}  finished=$ex  log_mtime=$(date -r $O/land-$s.log +%H:%M 2>/dev/null)"
done
date +%H:%M
cd /mnt/e/Nizam_e_Qanoon && ./nz psql -tAc "SELECT count(*) FROM source_observation WHERE scraper_version='recrawl-2026-10-20/1'"
