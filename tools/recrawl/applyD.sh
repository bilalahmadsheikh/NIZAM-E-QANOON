#!/bin/bash
# applyD.sh DOC [SUFFIX] : record patches/patch-DOC[SUFFIX].json, then replay (waiting for the lock)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
F=.artifacts/recrawl-queue/patches/patch-$1${2:+$2}.json
.venv/bin/python tools/recrawl/fill_patch.py $F || exit 1
OUT=$(.venv/bin/python tools/record_curation_patch.py --readings $F --apply 2>&1); echo "$OUT" | grep -E "refused|recorded|:" | grep -v "block now" | head -8
echo "$OUT" | grep -q "recorded 0 " && { echo "nothing recorded -- no replay"; exit 1; }
bash tools/recrawl/replayD.sh $1
