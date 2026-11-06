#!/bin/bash
# many.sh DOC... : render each patch's pages, apply each patch-DOC.json, show units left
cd /mnt/e/Nizam_e_Qanoon
for d in "$@"; do
  for p in $(.venv/bin/python -c "import json;print(' '.join(sorted({str(r['page_no']) for r in json.load(open('.artifacts/recrawl-queue/patches/patch-$d.json'))})))"); do bash tools/recrawl/render.sh $d $p 70 >/dev/null; done
  bash tools/recrawl/patch.sh $d apply 2>&1 | grep -E "refused|matched|not |required|^released|^[0-9]+\|" | grep -v locator
done
.venv/bin/python tools/recrawl/units_for.py "$@" 2>/dev/null | grep -v "^==="
