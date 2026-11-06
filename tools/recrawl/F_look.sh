#!/bin/bash
# F_look.sh DOC [DPI] : release state, open units, and renders of every page an open unit sits on (read-only + renders)
cd /mnt/e/Nizam_e_Qanoon
bash tools/recrawl/rel.sh $1 | tail -1
U=$(.venv/bin/python tools/recrawl/units_for.py $1)
echo "$U"
for p in $(echo "$U" | grep -oE '(kept|demoted) p[0-9]+' | grep -oE '[0-9]+' | sort -un); do
  bash tools/recrawl/render.sh $1 $p ${2:-80} | cut -c1-80
done
