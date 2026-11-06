#!/bin/bash
# ocr_manual.sh DOC PACK : validate + adjudicate an owner export with rejected pages, then dry-run promotion
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
E=.artifacts/ocr-review-exports/ocr-review-doc-$1.json
.venv/bin/python tools/validate_ocr_review_export.py $E --pack .artifacts/$2 | tail -1
.venv/bin/python tools/evidence/adjudicate_ocr_review_export.py $E --apply | tail -1
.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $1 2>&1 | tail -3
