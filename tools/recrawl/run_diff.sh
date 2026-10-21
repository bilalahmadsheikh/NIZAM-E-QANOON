#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for s in "$@"; do
  .venv/bin/python tools/recrawl/diff_listing.py $O/listing-$s.jsonl $O/missing-$s.jsonl 2>&1 | head -45
done
