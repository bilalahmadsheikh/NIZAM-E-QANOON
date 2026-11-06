#!/bin/bash
# Re-segment (identical rebuild) every document the released-count guard flags, with the declaration; repeat until clean.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for pass in 1 2 3; do
  IDS=$(.venv/bin/python tools/released_count_guard.py 2>&1 | grep -oE "UNDECLARED: document [0-9]+" | grep -oE "[0-9]+$" | paste -sd,)
  [ -z "$IDS" ] && { echo "guard clean"; break; }
  echo "pass $pass declaring: $IDS"
  .venv/bin/python -m nizam.workers.segment --documents "$IDS" --include-review --quiet \
    --approve-release-change "recrawl 2026-10-20: released after rule adjudication of its open units -- new released expression" 2>&1 | grep -E "segmented|failed"
done
.venv/bin/python tools/released_count_guard.py 2>&1 | tail -1
./nz psql -tAc "SELECT 'released '||count(*) FROM v_release_instrument"
