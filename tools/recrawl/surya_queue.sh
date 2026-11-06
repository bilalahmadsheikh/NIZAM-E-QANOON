#!/bin/bash
# surya_queue.sh : (1) finish the q1 review queue's small documents (big ones set aside), (2) page-targeted re-reads of
# held documents' dispute/gap pages. One CPU Surya server at a time. Resumable (run_surya_ocr.sh skips done work).
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
Q=/mnt/e/nizam-data/ocr
mkdir -p $Q/q1r-input-later
for d in 7847 7849 9326; do [ -f $Q/q1r-input/$d.pdf ] && mv $Q/q1r-input/$d.pdf $Q/q1r-input-later/; done
SURYA_LOG=$Q/q1r-output/run.log bash tools/run_surya_ocr.sh $Q/q1r-input $Q/q1r-output
.venv/bin/python tools/recrawl/pt_inputs.py .artifacts/recrawl-queue/targetpages.json 4 $Q/pt-input
mkdir -p $Q/pt-output
SURYA_LOG=$Q/pt-output/run.log bash tools/run_surya_ocr.sh $Q/pt-input $Q/pt-output
echo "surya queue finished"
