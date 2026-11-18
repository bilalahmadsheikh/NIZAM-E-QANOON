#!/usr/bin/env bash
# baseline.sh DOCS OUTDIR : dry-run documents as they stand (no new readings); a tree dump means the stored release
# does not rebuild identically today (drift), independent of any batch.
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=. PYTHONIOENCODING=utf-8
rm -rf "$2"; mkdir -p "$2/dump"
.venv/bin/python -m nizam.workers.segment --documents "$1" --redo --include-review --dry-run --quiet \
  --release-diff "$2/diff.jsonl" --release-tree-dump "$2/dump" 2>&1 | grep -E 'ERROR|analysed' | cut -c1-220
echo "documents that do not rebuild identically: $(ls "$2/dump" | sed 's/_.*//' | sort -u | paste -sd, -)"
