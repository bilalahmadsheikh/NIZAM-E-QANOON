#!/bin/bash
# sweep.sh DOC... : for each RELEASED document, one at a time: set aside its running heads and amendment-note blocks
# (sweep.py -> blockfix.py), record, replay under the release gate (a replay that would fail the gate rolls back, so a
# release is never lost), and report the release state and leakscan.py before/after. Appends to sweep-log.txt.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
LOG=.artifacts/recrawl-queue/sweep-log.txt
for D in "$@"; do
  B=$(.venv/bin/python tools/recrawl/leakscan.py --quiet $D | head -1)
  S=.artifacts/recrawl-queue/specs/sweep-$D.json; P=.artifacts/recrawl-queue/patches/patch-${D}sw.json
  N=$(.venv/bin/python tools/recrawl/sweep.py $D $S)
  if grep -q ': 0 blocks' <<< "$N"; then echo "$D | nothing to set aside | $B" >> $LOG; continue; fi
  PG=$(python3 -c "import json;print(' '.join(json.load(open('$S'))['pages']))")
  bash .artifacts/recrawl-queue/render_pages.sh $D 60 $PG >/dev/null 2>&1
  if ! .venv/bin/python tools/recrawl/blockfix.py $S $P >/dev/null 2>&1; then echo "$D | blockfix refused | $B" >> $LOG; continue; fi
  REC=$(.venv/bin/python tools/record_curation_patch.py --readings $P --apply 2>&1 | grep -oE 'recorded [0-9]+')
  SEG=$(.venv/bin/python -m nizam.workers.segment --document $D --redo --include-review \
        --approve-release-change "recrawl sweep 2026-10-29: running heads and amendment notes set aside (sweep.py)" 2>&1 \
        | grep -oE 'segmented [0-9]+, failed [0-9]+|ERROR.*' | head -2 | tr '\n' ' ' | cut -c1-160)
  A=$(.venv/bin/python tools/recrawl/leakscan.py --quiet $D | head -1)
  echo "$D | $N | $REC | $SEG | $(bash tools/recrawl/rel.sh $D | tail -1) | before: $B | after: $A" >> $LOG
done
echo "sweep done: $(bash tools/recrawl/rel.sh 0 | head -1)" >> $LOG
