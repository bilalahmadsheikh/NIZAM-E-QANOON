#!/bin/bash
# replayD.sh DOC : re-segment DOC (patches already recorded), retrying while another run holds the lock
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for i in $(seq 1 40); do
  OUT=$(.venv/bin/python -m nizam.workers.segment --document $1 --redo --include-review \
    --approve-release-change "recrawl queue 2026-10-22: source-read repair of doc $1 (agent D patches) -- new released expression" 2>&1)
  if echo "$OUT" | grep -q "holds the lock"; then sleep 15; continue; fi
  echo "$OUT" | tail -4; break
done
bash tools/recrawl/rel.sh $1
