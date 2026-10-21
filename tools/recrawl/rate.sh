#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon
./nz psql -tAc "SELECT count(*) FILTER (WHERE fetched_at > now() - interval '10 minutes') AS last10min, count(*) AS total FROM source_observation WHERE scraper_version='recrawl-2026-10-20/1'"
echo "jobs running: $(ps -eo args | grep -c '[l]and_missing')"
