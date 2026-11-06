#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
OUT=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $1 --allow-partial --apply 2>&1); echo "$OUT" | tail -2
NEW=$(grep -oE "$1 -> [0-9]+" <<< "$OUT" | grep -oE "[0-9]+$" | tail -1); echo NEW=$NEW
[ -n "$NEW" ] && .venv/bin/python -m nizam.workers.segment --documents $NEW --include-review --quiet 2>&1 | grep -E "ERROR|segmented [0-9]"
[ -n "$NEW" ] && .venv/bin/python tools/recrawl/tree.py $NEW
