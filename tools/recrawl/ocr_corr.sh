#!/bin/bash
# ocr_corr.sh DOC : adjudicate an export with owner corrections, then the normal apply path
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
.venv/bin/python tools/evidence/adjudicate_ocr_review_export.py .artifacts/ocr-review-exports/ocr-review-doc-$1.json --corrections .artifacts/ocr-review-exports/chat-2026-10-24/corrections-doc-$1.json --apply | tail -2
OUT=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $1 --apply 2>&1); echo "$OUT" | grep -E "promote|SKIP" | tail -2
NEW=$(grep -oE "$1 -> [0-9]+" <<< "$OUT" | grep -oE "[0-9]+$" | tail -1); echo NEW=$NEW
[ -n "$NEW" ] && .venv/bin/python -m nizam.workers.segment --documents $NEW --include-review --quiet 2>&1 | grep -E "ERROR|segmented [0-9]"
