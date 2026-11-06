#!/bin/bash
# patch.sh DOC [apply]: record the patch file .artifacts/recrawl-queue/patches/patch-DOC.json (dry run unless 'apply'),
# then dry-run the replay and show the S7/TOC outcome; with 'apply' the replay is written.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
F=.artifacts/recrawl-queue/patches/patch-$1${3:+$3}.json
.venv/bin/python tools/recrawl/fill_patch.py $F || exit 1
if [ "$2" = apply ]; then
  OUT=$(.venv/bin/python tools/record_curation_patch.py --readings $F --apply 2>&1); echo "$OUT" | tail -3
  echo "$OUT" | grep -q "recorded 0 " && { echo "nothing recorded -- no replay"; exit 1; }
  .venv/bin/python -m nizam.workers.segment --document $1 --redo --include-review \
    --approve-release-change "recrawl queue 2026-10-21: source-read repair of doc $1 (patch-$1.json) -- new released expression" 2>&1 | tail -6
  bash tools/recrawl/rel.sh $1
else
  .venv/bin/python tools/record_curation_patch.py --readings $F 2>&1 | tail -4
fi
