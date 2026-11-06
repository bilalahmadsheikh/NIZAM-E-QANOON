#!/bin/bash
# q1pack.sh: import Surya results for finished q1 documents (non-destructive candidates) and build one review pack.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
OUT=/mnt/e/nizam-data/ocr/q1r-output; IN=/mnt/e/nizam-data/ocr/q1r-input
ARGS=""
DONE=" 5526 5531 5532 5606 5610 5645 5679 5720 "
for d in $(ls $OUT | grep -E '^[0-9]+$'); do
  [[ "$DONE" == *" $d "* ]] && continue
  R=$OUT/$d/results.json
  [ -f "$R" ] || { echo "skip $d (no results.json)"; continue; }
  .venv/bin/python -m nizam.workers.import_surya_candidates $R 2>&1 | tail -1
  ARGS="$ARGS --document $d"
done
.venv/bin/python tools/build_ocr_review_pack.py $ARGS --input $IN --results $OUT --out .artifacts/ocr-review-pack-q1b 2>&1 | tail -3
