#!/bin/bash
# rec_only.sh LINES SUFFIX : build + record compact patches WITHOUT replay (for split documents: re-run lsplit.sh after)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for d in $(.venv/bin/python tools/recrawl/mkpatch.py $1 $2); do
  F=.artifacts/recrawl-queue/patches/patch-$d$2.json
  .venv/bin/python tools/recrawl/fill_patch.py $F >/dev/null && .venv/bin/python tools/record_curation_patch.py --readings $F --apply 2>&1 | tail -1 | sed "s/^/$d: /"
done
