#!/bin/bash
# replay.sh DOC [DOC ...] : re-segment each doc (recorded patches/readings take effect), then show its release state
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for d in "$@"; do
  .venv/bin/python -m nizam.workers.segment --document $d --redo --include-review \
    --approve-release-change "recrawl queue 2026-10-23: source-read repair of doc $d (recorded curation patches) -- new released expression" 2>&1 | grep -iE "lock|error" | head -2
  bash tools/recrawl/rel.sh $d | tail -1
done
bash tools/recrawl/rel.sh 0 2>/dev/null | head -1
