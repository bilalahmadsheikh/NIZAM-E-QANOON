#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/recrawl/chat_export.py 5875
.venv/bin/python tools/recrawl/chat_export.py 5800
.venv/bin/python tools/recrawl/chat_export.py 5785 2
.venv/bin/python tools/recrawl/chat_export.py 5819 15 23
for d in 5875 5800 5785 5819; do .venv/bin/python tools/validate_ocr_review_export.py .artifacts/ocr-review-exports/ocr-review-doc-$d.json --pack .artifacts/ocr-review-pack-q1c | tail -1; done
