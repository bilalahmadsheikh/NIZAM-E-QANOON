#!/bin/bash
O=/mnt/e/nizam-data/recrawl-2026-10-20
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for s in "$@"; do
  ( .venv/bin/python tools/recrawl/land_missing.py $O/missing-$s.jsonl $O/landed-$s.json --apply > $O/land-$s.log 2>&1; echo "exit $?" >> $O/land-$s.log ) &
done
wait
for s in "$@"; do echo "== $s: $(tail -2 $O/land-$s.log | tr '\n' ' ')"; done
