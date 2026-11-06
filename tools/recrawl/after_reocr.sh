#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python -m nizam.workers.segment --documents 8565 --include-review --quiet \
  --approve-release-change "recrawl 2026-10-20: released after rule adjudication of its S7 units -- new released expression" 2>&1 | grep -E "segmented|failed"
.venv/bin/python tools/released_count_guard.py 2>&1 | tail -2
./nz psql -tAc "SELECT 'released '||count(*) FROM v_release_instrument"
bash tools/recrawl/queue.sh 2>&1 | sed -n 3,40p
