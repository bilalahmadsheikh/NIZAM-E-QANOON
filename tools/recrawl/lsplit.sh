#!/bin/bash
# lsplit.sh DOC : lead split -- plan (G_mkplan), anchors (anchor.py --apply when needed), materialize, show state
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/policy_apply.py split $1 >/dev/null
for p in $(.venv/bin/python -c "import json;print(' '.join(map(str,json.load(open('.artifacts/recrawl-queue/splits/spec-$1.json'))['pages'])))"); do bash tools/recrawl/render.sh $1 $p 70 >/dev/null; done
[ -f tools/evidence/multi-instrument-plans/doc-$1.json ] || .venv/bin/python tools/recrawl/G_mkplan.py .artifacts/recrawl-queue/splits/spec-$1.json || exit 1
A=$(.venv/bin/python tools/recrawl/anchor.py $1 2>&1); echo "$A" | tail -2
if ! echo "$A" | grep -qi "nothing to anchor\|no anchor\|0 anchor"; then .venv/bin/python tools/recrawl/anchor.py $1 --apply 2>&1 | tail -1; fi
bash tools/recrawl/split.sh $1 apply 2>&1 | grep -E "^released|^[0-9]+\||Error|error|S7|TOC" 
.venv/bin/python tools/recrawl/tree.py $1 section,article,schedule 2>/dev/null
