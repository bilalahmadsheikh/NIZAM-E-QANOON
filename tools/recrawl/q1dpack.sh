#!/bin/bash
# q1dpack.sh : review pack q1d -- the Surya-finished q1 documents after q1c (smallest first in the index)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
OUT=/mnt/e/nizam-data/ocr/q1r-output; IN=/mnt/e/nizam-data/ocr/q1r-input
ARGS=""
for d in 7551 7566 7606 7612 7656 7672 7677 7678 7697 7699 7700 7740 7741 7761 7783 7550 7771 7798 7706 7742; do
  [ -f $OUT/$d/results.json ] || continue
  ARGS="$ARGS --document $d"
done
.venv/bin/python tools/build_ocr_review_pack.py $ARGS --input $IN --results $OUT --out .artifacts/ocr-review-pack-q1d 2>&1 | tail -1 | cut -c1-300
