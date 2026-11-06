#!/bin/bash
# surya_queue2.sh : (1) page-targeted re-reads of held E4 documents, documents needing fewest pages first
# (pt-in-1..4, staged by tools/recrawl/ptq.py), then (2) the small remaining q1r documents (<= 7 pages; larger ones
# moved to q1r-input-later). One CPU Surya server at a time. Resumable (run_surya_ocr.sh skips done work).
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
Q=/mnt/e/nizam-data/ocr
mkdir -p $Q/q1r-input-later $Q/pt-output
for f in $Q/q1r-input/*.pdf; do
  n=$(.venv/bin/python -c "import pymupdf,sys;print(pymupdf.open(sys.argv[1]).page_count)" $f)
  [ "$n" -gt 7 ] && [ ! -f $Q/q1r-output/$(basename $f .pdf)/results.json ] && mv $f $Q/q1r-input-later/
done
for k in 1 2 3 4; do
  [ -d $Q/pt-in-$k ] && SURYA_LOG=$Q/pt-output/run.log bash tools/run_surya_ocr.sh $Q/pt-in-$k $Q/pt-output
done
SURYA_LOG=$Q/q1r-output/run.log bash tools/run_surya_ocr.sh $Q/q1r-input $Q/q1r-output
echo "surya queue 2 finished"
