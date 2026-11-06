#!/bin/bash
# tocrec.sh LINES NAME [apply] : build contents-gap readings and record them (dry unless apply)
cd /mnt/e/Nizam_e_Qanoon; export PYTHONPATH=.
O=.artifacts/recrawl-queue/readings/toc-$2.json
.venv/bin/python tools/recrawl/tocread.py $1 $O && .venv/bin/python tools/adjudicate_toc_from_source.py --readings $O ${3:+--apply} 2>&1 | tail -12
