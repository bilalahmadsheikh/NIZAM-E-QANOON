#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
cd /mnt/e/Nizam_e_Qanoon
python3 tools/recrawl/list_portals.py punjab $O/listing-punjab.jsonl > $O/list-punjab.log 2>&1; tail -1 $O/list-punjab.log
bash tools/recrawl/run_diff.sh punjab
bash tools/recrawl/run_land.sh punjab
