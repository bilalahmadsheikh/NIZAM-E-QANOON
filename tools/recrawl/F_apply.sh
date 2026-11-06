#!/bin/bash
# F_apply.sh DOC [SUFFIX] : fill, record patch-DOC[SUFFIX].json, then replay with lock retry (F_replay.sh)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
F=.artifacts/recrawl-queue/patches/patch-$1${2:-}.json
.venv/bin/python tools/recrawl/fill_patch.py $F || exit 1
OUT=$(.venv/bin/python tools/record_curation_patch.py --readings $F --apply 2>&1); echo "$OUT" | tail -2
echo "$OUT" | grep -q "recorded 0 " && { echo "nothing recorded -- no replay"; exit 1; }
bash tools/recrawl/F_replay.sh $1
