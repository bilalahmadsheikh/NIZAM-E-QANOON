#!/bin/bash
# split.sh DOC [apply] : build plan from .artifacts/recrawl-queue/splits/spec-DOC.json (once), dry-run / apply the materializer
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/policy_apply.py split $1 >/dev/null
for p in $(.venv/bin/python -c "import json;print(' '.join(map(str,json.load(open('.artifacts/recrawl-queue/splits/spec-$1.json'))['pages'])))"); do bash tools/recrawl/render.sh $1 $p 70 >/dev/null; done
[ -f tools/evidence/multi-instrument-plans/doc-$1.json ] || .venv/bin/python tools/recrawl/mkplan.py .artifacts/recrawl-queue/splits/spec-$1.json || exit 1
if [ "$2" = apply ]; then
  .venv/bin/python tools/materialize_multi_instrument.py --document $1 --apply \
     --approve-release-change "owner policy q1 split (22 Oct): reviewed plan doc-$1 -- new released expression" 2>&1 | tail -4
  bash tools/recrawl/rel.sh $1
  .venv/bin/python tools/recrawl/units_for.py $1 2>/dev/null
else
  .venv/bin/python tools/materialize_multi_instrument.py --document $1 --summary-only 2>&1 | tail -12
fi
