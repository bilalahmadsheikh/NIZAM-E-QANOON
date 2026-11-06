#!/bin/bash
# pt_post.sh : import every finished page-targeted Surya result not yet imported, then for each document whose staged
# target pages are all imported, the q4 agreement dry run (tools/recrawl/ocr_policy.py). Writes candidates only.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
Q=/mnt/e/nizam-data/ocr; OUT=$Q/pt-output; DOCS=""
for r in $OUT/*-page*/results.json; do
  [ -f "$r" ] || continue; stem=$(basename $(dirname $r)); d=${stem%%-page*}; p=${stem##*-page}
  N=$(./nz psql -tAc "SELECT count(*) FROM page_ocr_candidate WHERE document_id=$d AND page_no=$p AND engine LIKE 'surya%'" | tr -d '[:space:]')
  [ "$N" = "0" ] && .venv/bin/python -m nizam.workers.import_surya_candidates $r 2>&1 | tail -1
  DOCS="$DOCS $d"
done
READY=""
for d in $(echo $DOCS | tr ' ' '\n' | sort -u); do
  want=$(ls $Q/pt-in-*/$d-page*.pdf 2>/dev/null | wc -l); have=$(ls -d $OUT/$d-page*/ 2>/dev/null | while read x; do [ -f $x/results.json ] && echo y; done | wc -l)
  [ "$have" -ge "$want" ] && READY="$READY $d"
done
echo "ready:$READY"
[ -n "$READY" ] && .venv/bin/python tools/recrawl/ocr_policy.py $READY
