#!/bin/bash
# c_replay.sh DOC : replay one document (approved as a source-read repair) and print its release state
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python -m nizam.workers.segment --document $1 --redo --include-review \
  --approve-release-change "recrawl queue 2026-10-22: source-read repair of doc $1 (agent C) -- new released expression" 2>&1 | grep -E "ok|fail|rror|segmented|another|lock" | tail -4
bash tools/recrawl/rel.sh $1
