#!/bin/bash
# readings.sh MANIFEST|- LINES NAME [apply] : build readings, dry-run (or apply) them
cd /mnt/e/Nizam_e_Qanoon
.venv/bin/python tools/recrawl/mkread.py "$1" "$2" .artifacts/recrawl-queue/readings/$3.json || exit 1
if [ "$4" = apply ]; then
  .venv/bin/python tools/adjudicate_s7_from_source.py --readings .artifacts/recrawl-queue/readings/$3.json --apply | grep -v " -> accept_non_citable"
else
  .venv/bin/python tools/adjudicate_s7_from_source.py --readings .artifacts/recrawl-queue/readings/$3.json | grep -v " -> accept_non_citable"
fi
