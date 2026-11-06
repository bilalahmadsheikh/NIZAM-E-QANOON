#!/bin/bash
# G_split.sh DOC : agent G -- renders the spec pages, builds the plan with G_mkplan.py (multi-span aware; once),
# then split.sh's dry-run summary and anchor.py's dry run. Apply with G_apply.sh DOC.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/policy_apply.py split $1 >/dev/null
for p in $(.venv/bin/python -c "import json;print(' '.join(map(str,json.load(open('.artifacts/recrawl-queue/splits/spec-$1.json'))['pages'])))"); do bash tools/recrawl/render.sh $1 $p 70 >/dev/null; done
[ -f tools/evidence/multi-instrument-plans/doc-$1.json ] || .venv/bin/python tools/recrawl/G_mkplan.py .artifacts/recrawl-queue/splits/spec-$1.json || exit 1
bash tools/recrawl/split.sh $1 | grep -E 'expressions|provisions|s7_cand|blocks|Error|error' 
.venv/bin/python tools/recrawl/anchor.py $1 2>&1 | tail -6
