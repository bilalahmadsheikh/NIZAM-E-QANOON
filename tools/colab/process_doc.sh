#!/bin/bash
# process_doc.sh DOC : after a Colab Surya re-read is imported -- delegated q5 acceptance when the in-memory trial
# shows a strictly better tree (tools/recrawl/ocr_trial_accept.py), promotion into a new revision (partial for E4,
# whole for E2/E3), segmentation for review, then the revision's tree summary and pending units. verify_ocr and the
# release are NOT done here: tools/recrawl/finish.sh OLD NEW, after the tree is read.
set -uo pipefail
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
D=$1; q() { ./nz psql -tAc "$1" | tr -d '[:space:]'; }
.venv/bin/python tools/recrawl/ocr_trial_accept.py $D --apply "${@:2}" | tail -3; [ ${PIPESTATUS[0]} -eq 0 ] || exit 1
LANE=$(q "SELECT lane FROM document WHERE id=$D")
FLAGS="--allow-partial"; [ "$LANE" = "E2" ] && FLAGS="--allow-text-layer"; [ "$LANE" = "E3" ] && FLAGS="--allow-mixed"
OUT=$(.venv/bin/python tools/promote_ocr_adjudicated.py --document-id $D $FLAGS --apply 2>&1)
NEW=$(grep -oE "$D -> [0-9]+" <<< "$OUT" | grep -oE '[0-9]+$' | tail -1)
[ -n "$NEW" ] || { echo "$OUT" | tail -4; echo "STOP: not promoted"; exit 1; }
echo "DOC $D -> NEW=$NEW"
.venv/bin/python -m nizam.workers.segment --documents $NEW --include-review --quiet 2>&1 | grep -E "ERROR|segmented [0-9]"
bash tools/recrawl/rel.sh $NEW | tail -1
.venv/bin/python tools/recrawl/units_for.py $NEW 2>/dev/null | head -12
