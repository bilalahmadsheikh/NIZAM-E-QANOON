#!/bin/bash
# ocr_verify.sh NEWDOC... : verify_ocr LAST on promoted revisions whose tree has been read, then release state.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
for d in "$@"; do .venv/bin/python -m nizam.workers.verify_ocr --document-id $d --verbose 2>&1 | tail -2; done
bash tools/recrawl/rel.sh "$@"
