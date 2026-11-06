#!/bin/bash
# qrem.sh : q1r input docs without output yet, with page counts; and the targeted-page plan size (read-only)
cd /mnt/e/Nizam_e_Qanoon; Q=/mnt/e/nizam-data/ocr; T=0
for f in $Q/q1r-input/*.pdf; do d=$(basename $f .pdf); [ -f $Q/q1r-output/$d/results.json ] && continue
  n=$(.venv/bin/python -c "import pymupdf,sys;print(pymupdf.open(sys.argv[1]).page_count)" $f); T=$((T+n)); echo "$d $n"; done
echo "remaining q1r pages: $T"; ls -la --time-style=+%H:%M $Q/q1r-output | tail -3; date +%H:%M
.venv/bin/python -c "import json;d=json.load(open('.artifacts/recrawl-queue/targetpages.json'));print('targetpages entries',len(d))"
