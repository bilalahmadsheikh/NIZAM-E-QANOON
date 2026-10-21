#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
cd /mnt/e/Nizam_e_Qanoon
python3 tools/recrawl/list_portals.py balochistan_gov $O/listing-balochistan_gov.jsonl > $O/list-balochistan_gov.log 2>&1; tail -1 $O/list-balochistan_gov.log
bash tools/recrawl/run_diff.sh balochistan_gov
bash tools/recrawl/run_land.sh balochistan_gov
