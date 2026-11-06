#!/bin/bash
# sweep_restore.sh DOC... : record specs/restore-DOC.json (sweep_restore.py) and replay under the release gate
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for D in "$@"; do
  S=.artifacts/recrawl-queue/specs/restore-$D.json
  PG=$(python3 -c "import json;print(' '.join(json.load(open('$S'))['pages']))")
  bash .artifacts/recrawl-queue/render_pages.sh $D 60 $PG >/dev/null 2>&1
  .venv/bin/python tools/recrawl/blockfix.py $S .artifacts/recrawl-queue/patches/patch-${D}rs.json >/dev/null || { echo "$D blockfix refused"; continue; }
  REC=$(.venv/bin/python tools/record_curation_patch.py --readings .artifacts/recrawl-queue/patches/patch-${D}rs.json --apply 2>&1 | grep -oE 'recorded [0-9]+|refused.*' | head -2 | tr '\n' ' ')
  SEG=$(.venv/bin/python -m nizam.workers.segment --document $D --redo --include-review \
        --approve-release-change "recrawl 2026-10-29: law text restored that the sweep had set aside with a running head" 2>&1 \
        | grep -oE 'segmented [0-9]+, failed [0-9]+|ERROR.*' | head -1 | cut -c1-160)
  echo "$D | $REC | $SEG | $(bash tools/recrawl/rel.sh $D | tail -1)"
done
