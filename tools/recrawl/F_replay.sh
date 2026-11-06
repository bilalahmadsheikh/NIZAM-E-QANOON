#!/bin/bash
# F_replay.sh DOC : re-segment DOC with its recorded patches (waits for the segmentation lock), then release state
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for i in $(seq 1 60); do
  OUT=$(.venv/bin/python -m nizam.workers.segment --document $1 --redo --include-review \
    --approve-release-change "recrawl queue 2026-10-21: source-read repair of doc $1 (patch-$1.json) -- new released expression" 2>&1)
  echo "$OUT" | grep -q "holds the lock" || break
  sleep 5
done
echo "$OUT" | tail -4
bash tools/recrawl/rel.sh $1
