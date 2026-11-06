#!/bin/bash
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
for d in "$@"; do .venv/bin/python tools/recrawl/retire_stale.py $d --apply | tail -1; .venv/bin/python -m nizam.workers.segment --documents $d --include-review --quiet 2>&1 | grep -E "ERROR|segmented [0-9]"; done
