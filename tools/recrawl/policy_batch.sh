#!/bin/bash
# policy_batch.sh [apply] : import finished Surya results not yet imported, then run the q4 agreement policy on them
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
OUT=/mnt/e/nizam-data/ocr/q1r-output
DONE=" 5526 5531 5532 5606 5610 5645 5679 5720 5721 5736 5750 5760 5785 5800 5819 5854 5875 7539 7544 7547 7548 "
DOCS=""
for d in $(ls $OUT | grep -E '^[0-9]+$'); do
  [[ "$DONE" == *" $d "* ]] && continue
  [ -f $OUT/$d/results.json ] || continue
  N=$(./nz psql -tAc "SELECT count(*) FROM page_ocr_candidate WHERE document_id=$d AND engine LIKE 'surya%'" | tr -d '[:space:]')
  [ "$N" = "0" ] && .venv/bin/python -m nizam.workers.import_surya_candidates $OUT/$d/results.json 2>&1 | tail -1
  DOCS="$DOCS $d"
done
echo "docs:$DOCS"
.venv/bin/python tools/recrawl/ocr_policy.py $DOCS ${1:+--apply}
