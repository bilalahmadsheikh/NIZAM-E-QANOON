#!/bin/bash
# List all four reachable portals in parallel; each writes its own JSONL and log.
O=/mnt/e/nizam-data/recrawl-2026-10-20; mkdir -p $O
cd /mnt/e/Nizam_e_Qanoon
for s in federal kp sindh balochistan; do
  ( python3 tools/recrawl/list_portals.py $s $O/listing-$s.jsonl > $O/list-$s.log 2>&1; echo "exit $?" >> $O/list-$s.log ) &
done
wait
for s in federal kp sindh balochistan; do echo "== $s: $(tail -2 $O/list-$s.log | tr '\n' ' ') lines=$(wc -l < $O/listing-$s.jsonl)"; done
